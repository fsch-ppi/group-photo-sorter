<?php

namespace OCA\GroupPhotoSorter\Command;

use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;
use OCA\GroupPhotoSorter\Service\FolderService;
use OCA\GroupPhotoSorter\Service\ConversionService;
use OCA\GroupPhotoSorter\Db\FolderMapper;
use OCA\GroupPhotoSorter\Db\ConversionTaskMapper;
use OCA\GroupPhotoSorter\Db\UploadStatsMapper;
use OCP\Files\IRootFolder;
use OCP\AppFramework\Db\DoesNotExistException;

class TestAppCommand extends Command {

    private FolderService $folderService;
    private ConversionService $conversionService;
    private FolderMapper $folderMapper;
    private ConversionTaskMapper $taskMapper;
    private UploadStatsMapper $statsMapper;
    private IRootFolder $rootFolder;

    public function __construct(
        FolderService $folderService,
        ConversionService $conversionService,
        FolderMapper $folderMapper,
        ConversionTaskMapper $taskMapper,
        UploadStatsMapper $statsMapper,
        IRootFolder $rootFolder
    ) {
        parent::__construct();
        $this->folderService = $folderService;
        $this->conversionService = $conversionService;
        $this->folderMapper = $folderMapper;
        $this->taskMapper = $taskMapper;
        $this->statsMapper = $statsMapper;
        $this->rootFolder = $rootFolder;
    }

    protected function configure(): void {
        $this->setName('group-photo-sorter:run-tests')
             ->setDescription('Run integration tests for the Group Photo Sorter app');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int {
        putenv('GPS_TESTING=1');
        $output->writeln("=================================================");
        $output->writeln("Running Group Photo Sorter CLI Integration Tests");
        $output->writeln("=================================================");
        
        $testFolderName = "Test_CLI_Folder_" . time();
        $testEventName = "test_cli_event";
        $testPath = "Photos/" . $testFolderName;
        
        // 1. Create a test folder configuration
        $output->writeln("1. Creating test folder configuration...");
        try {
            $folder = $this->folderService->create('admin', [
                'name' => $testFolderName,
                'event_name' => $testEventName,
                'nextcloud_folder_path' => $testPath,
                'naming_format' => 'DATE_EVENT',
                'jpeg_quality' => 85,
                'video_crf' => 24,
                'readme_message' => 'CLI Test Readme'
            ]);
            
            $output->writeln("   - Folder created with ID: " . $folder->getId());
            $output->writeln("   - Token: " . $folder->getToken());
            $output->writeln("   - Nextcloud Path: " . $folder->getNextcloudFolderPath());
        } catch (\Exception $e) {
            $output->writeln("<error>Failed to create test folder: " . $e->getMessage() . "</error>");
            return Command::FAILURE;
        }

        // 2. Generate a mock image file
        $output->writeln("2. Generating test image file...");
        $tempBaseDir = sys_get_temp_dir() . '/gps_uploads';
        if (!file_exists($tempBaseDir)) {
            mkdir($tempBaseDir, 0755, true);
        }
        $tempInputPath = $tempBaseDir . '/test_cli_input_' . time() . '.jpg';
        
        // Find python bin
        $pythonBin = __DIR__ . '/../../.venv/bin/python3';
        if (!file_exists($pythonBin)) {
            $pythonBin = __DIR__ . '/../../venv/bin/python3';
            if (!file_exists($pythonBin)) {
                $pythonBin = 'python3';
            }
        }
        $cmd = escapeshellarg($pythonBin) . " -c 'from PIL import Image; img = Image.new(\"RGB\", (100, 100), color = \"red\"); img.save(\"" . $tempInputPath . "\")' 2>&1";
        $execOutput = [];
        $returnVal = -1;
        @exec($cmd, $execOutput, $returnVal);
        
        if ($returnVal !== 0 || !file_exists($tempInputPath) || filesize($tempInputPath) === 0) {
            $output->writeln("<error>Failed to generate test image file: " . implode("\n", $execOutput) . "</error>");
            $this->deleteFolderSafely($folder->getId());
            return Command::FAILURE;
        }
        $output->writeln("   - Test image generated at: " . $tempInputPath);

        // 3. Create a conversion task
        $output->writeln("3. Queuing conversion task...");
        try {
            $taskId = $this->conversionService->createTask(
                $folder->getId(),
                $tempInputPath,
                'cli_test_image.jpg',
                false
            );
            $output->writeln("   - Task created with ID: " . $taskId);
        } catch (\Exception $e) {
            $output->writeln("<error>Failed to create task: " . $e->getMessage() . "</error>");
            @unlink($tempInputPath);
            $this->deleteFolderSafely($folder->getId());
            return Command::FAILURE;
        }

        // 4. Process the conversion queue
        $output->writeln("4. Processing conversion queue...");
        try {
            // Claim our specific test task to prevent other queued tasks from taking precedence
            $task = $this->taskMapper->find($taskId);
            $this->taskMapper->claimTask($taskId, 999999);
            
            // Run converter script synchronously on the test image
            $converterScript = __DIR__ . '/../../bin/converter.py';
            $pythonBin = __DIR__ . '/../../.venv/bin/python3';
            if (!file_exists($pythonBin)) {
                $pythonBin = __DIR__ . '/../../venv/bin/python3';
                if (!file_exists($pythonBin)) {
                    $pythonBin = 'python3';
                }
            }
            $cmd = escapeshellarg($pythonBin) . " " . escapeshellarg($converterScript) . " convert-image " . 
                   escapeshellarg($task->getTempPath()) . " " . 
                   escapeshellarg($task->getOutputPath()) . " " . 
                   escapeshellarg($folder->getJpegQuality());
            
            $cmdOutput = [];
            $retVal = -1;
            exec($cmd . " 2>&1", $cmdOutput, $retVal);
            
            if ($retVal !== 0) {
                $output->writeln("<error>Python converter failed (code $retVal): " . implode("\n", $cmdOutput) . "</error>");
            }
            
            // Run queue processing to let Nextcloud service finalize our claimed and converted task
            $result = $this->conversionService->processQueue();
            $output->writeln("   - Processed: " . $result['processed']);
            $output->writeln("   - Completed: " . $result['completed']);
            $output->writeln("   - Failed: " . $result['failed']);
        } catch (\Exception $e) {
            $output->writeln("<error>Queue processing threw exception: " . $e->getMessage() . "</error>");
            $this->deleteFolderSafely($folder->getId());
            return Command::FAILURE;
        }

        // 5. Verify task completion and output file in Nextcloud VFS
        $output->writeln("5. Verifying results...");
        
        $taskExists = true;
        $dbTask = null;
        try {
            $dbTask = $this->taskMapper->find($taskId);
        } catch (DoesNotExistException $e) {
            $taskExists = false;
        }
        
        if (!$taskExists || $dbTask === null) {
            $output->writeln("<error>Assertion Failed: Task does not exist in gps_tasks database</error>");
            $this->deleteFolderSafely($folder->getId());
            return Command::FAILURE;
        }
        
        if ($dbTask->getStatus() !== 'completed') {
            $output->writeln("<error>Assertion Failed: Task status is " . $dbTask->getStatus() . " (expected completed)</error>");
            $output->writeln("   - Error message: " . ($dbTask->getErrorMessage() ?: 'None'));
            $this->deleteFolderSafely($folder->getId());
            return Command::FAILURE;
        }
        $output->writeln("   [OK] Task marked as completed in database");

        // Check if stats recorded it
        $stats = $this->statsMapper->getUploadCount($folder->getId());
        if ($stats !== 1) {
            $output->writeln("<error>Assertion Failed: Statistics show " . $stats . " uploads (expected 1)</error>");
            $this->deleteFolderSafely($folder->getId());
            return Command::FAILURE;
        }
        $output->writeln("   [OK] Upload recorded in statistics database");

        // Verify the file was written to Nextcloud's virtual filesystem
        try {
            $userFolder = $this->rootFolder->getUserFolder('admin');
            $vfsPath = "Photos/" . $testFolderName;
            if (!$userFolder->nodeExists($vfsPath)) {
                $output->writeln("<error>Assertion Failed: Folder not found in user storage: " . $vfsPath . "</error>");
                $this->deleteFolderSafely($folder->getId());
                return Command::FAILURE;
            }
            
            $ncFolderNode = $userFolder->get($vfsPath);
            $children = $ncFolderNode->getDirectoryListing();
            
            if (count($children) === 0) {
                $output->writeln("<error>Assertion Failed: No files created in user storage folder: " . $vfsPath . "</error>");
                $this->deleteFolderSafely($folder->getId());
                return Command::FAILURE;
            }
            $output->writeln("   [OK] File successfully written to Nextcloud storage");
        } catch (\Exception $e) {
            $output->writeln("<error>Verification failed: " . $e->getMessage() . "</error>");
            $this->deleteFolderSafely($folder->getId());
            return Command::FAILURE;
        }

        // 6. Clean up test data
        $output->writeln("6. Cleaning up test data...");
        try {
            // Delete physical folder in Nextcloud
            if (isset($userFolder) && $userFolder->nodeExists($vfsPath)) {
                $userFolder->get($vfsPath)->delete();
                $output->writeln("   [OK] Nextcloud physical folder cleaned up");
            }
            
            // Delete folder settings from db
            $this->deleteFolderSafely($folder->getId());
            $output->writeln("   [OK] Database settings cleaned up");
        } catch (\Exception $e) {
            $output->writeln("<warning>Cleanup failed: " . $e->getMessage() . "</warning>");
        }

        $output->writeln("=================================================");
        $output->writeln("<info>SUCCESS: All integration tests passed!</info>");
        $output->writeln("=================================================");
        
        return Command::SUCCESS;
    }

    /**
     * Safely pause the folder config before calling FolderService::delete
     */
    private function deleteFolderSafely(int $folderId): void {
        try {
            $this->folderService->update($folderId, 'admin', ['is_active' => false]);
        } catch (\Exception $e) {
            // Ignore error if folder doesn't exist
        }
        try {
            $this->folderService->delete($folderId, 'admin');
        } catch (\Exception $e) {
            // Ignore error
        }
    }
}
