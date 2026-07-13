<?php

namespace OCA\GroupPhotoSorter\Service;

use OCP\ICacheFactory;
use OCP\ICache;
use OCP\Security\ISecureRandom;
use OCP\AppFramework\Db\DoesNotExistException;
use OCA\GroupPhotoSorter\Db\ConversionTask;
use OCA\GroupPhotoSorter\Db\ConversionTaskMapper;
use OCA\GroupPhotoSorter\Db\FolderMapper;
use OCA\GroupPhotoSorter\Db\UploadStats;
use OCA\GroupPhotoSorter\Db\UploadStatsMapper;

class ConversionService {

    private ConversionTaskMapper $taskMapper;
    private FolderMapper $folderMapper;
    private UploadStatsMapper $statsMapper;
    private StorageService $storageService;
    private ICache $cache;
    private ISecureRandom $random;

    private int $maxConcurrentConversions = 4;
    private int $timeoutSeconds = 7200; // 2 hours

    public function __construct(
        ConversionTaskMapper $taskMapper,
        FolderMapper $folderMapper,
        UploadStatsMapper $statsMapper,
        StorageService $storageService,
        ICacheFactory $cacheFactory,
        ISecureRandom $random
    ) {
        $this->taskMapper = $taskMapper;
        $this->folderMapper = $folderMapper;
        $this->statsMapper = $statsMapper;
        $this->storageService = $storageService;
        $this->cache = $cacheFactory->createDistributed('group_photo_sorter');
        $this->random = $random;
    }

    /**
     * Create a new conversion task in pending state
     */
    public function createTask(
        int $folderId,
        string $tempPath,
        string $originalFilename,
        bool $isVideo
    ): string {
        $taskId = $this->random->generate(32, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789');
        
        // Define temporary output path in system temp dir
        $extension = $isVideo ? '.mp4' : '.jpg';
        $outputPath = sys_get_temp_dir() . '/gps_out_' . $taskId . $extension;

        $task = new ConversionTask();
        $task->setId($taskId);
        $task->setFolderId($folderId);
        $task->setStatus('pending');
        $task->setOriginalFilename($originalFilename);
        $task->setTempPath($tempPath);
        $task->setOutputPath($outputPath);
        $task->setCreatedAt(new \DateTime());
        $task->setUpdatedAt(new \DateTime());

        $this->taskMapper->insertTask($task);

        // Try to trigger queue processing asynchronously
        $this->triggerQueueProcessingAsync();

        return $taskId;
    }

    /**
     * Get a task by ID
     */
    public function getTask(string $taskId): ConversionTask {
        return $this->taskMapper->find($taskId);
    }

    /**
     * Run the queue processor
     */
    public function processQueue(): array {
        // Allow up to 3 parallel queue processor processes
        try {
            $activeProcesses = $this->cache->get('active_processes') ?: [];
            if (!is_array($activeProcesses)) {
                $activeProcesses = [];
            }
            // Clean up dead processes from the list
            $activeProcesses = array_filter($activeProcesses, function($pid) {
                return $pid > 0 && $this->isPidRunning($pid);
            });

            if (count($activeProcesses) >= 3) {
                return ['status' => 'busy', 'message' => 'Max parallel queue processors running'];
            }

            $currentPid = getmypid();
            $activeProcesses[] = $currentPid;
            $this->cache->set('active_processes', $activeProcesses, 300);

            $processedCount = 0;
            $failedCount = 0;
            $completedCount = 0;

            // 1. Check active/processing tasks
            $processingTasks = $this->taskMapper->findProcessing();
            foreach ($processingTasks as $task) {
                $pid = $task->getPid();
                
                if ($pid !== null && $this->isPidRunning($pid)) {
                    // Check timeout
                    $age = time() - $task->getUpdatedAt()->getTimestamp();
                    if ($age > $this->timeoutSeconds) {
                        // Kill process
                        $this->killPid($pid);
                        $this->markTaskFailed($task, 'Processing timed out');
                        $failedCount++;
                    }
                } else {
                    // Process is not running, check if output was created
                    if (file_exists($task->getOutputPath()) && filesize($task->getOutputPath()) > 0) {
                        // Success!
                        $this->finalizeTaskSuccess($task);
                        $completedCount++;
                    } else {
                        // Process died/failed without output
                        $logPath = $task->getTempPath() . '.log';
                        $error = 'Process exited with no output file';
                        if (file_exists($logPath)) {
                            $logContent = file_get_contents($logPath);
                            $error = substr($logContent, -1000); // Last 1000 chars of ffmpeg log
                        }
                        $this->markTaskFailed($task, $error);
                        $failedCount++;
                    }
                }
                $processedCount++;
            }

            // 2. Start new tasks if capacity allows
            $activeProcessingCount = count($this->taskMapper->findProcessing());
            $vacancies = $this->maxConcurrentConversions - $activeProcessingCount;

            if ($vacancies > 0) {
                $pendingTasks = $this->taskMapper->findPending();
                $tasksToStart = array_slice($pendingTasks, 0, $vacancies);

                foreach ($tasksToStart as $task) {
                    // Atomically claim the task
                    if (!$this->taskMapper->claimTask($task->getId(), getmypid())) {
                        continue;
                    }

                    // Set status/pid locally to match claimed state
                    $task->setStatus('processing');
                    $task->setPid(getmypid());
                    $task->setUpdatedAt(new \DateTime());

                    try {
                        $folder = $this->folderMapper->find($task->getFolderId());
                    } catch (DoesNotExistException $e) {
                        $this->markTaskFailed($task, 'Folder no longer exists');
                        $failedCount++;
                        continue;
                    }

                    // Check if video or image
                    $ext = strtolower(pathinfo($task->getOriginalFilename(), PATHINFO_EXTENSION));
                    $videoExts = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'hevc', 'm4v', 'wmv', 'flv', '3gp'];
                    $isVideo = in_array($ext, $videoExts, true);

                    if ($isVideo) {
                        // Spawn background FFmpeg
                        if ($this->startVideoConversion($task, $folder->getVideoCrf())) {
                            // Video conversion is async, doesn't increment completedCount yet
                        } else {
                            $failedCount++;
                        }
                    } else {
                        // Inline Image Conversion (since we are in background script)
                        if ($this->startImageConversion($task, $folder->getJpegQuality())) {
                            $completedCount++;
                        } else {
                            $failedCount++;
                        }
                    }
                    $processedCount++;
                }
            }

            return [
                'status' => 'success',
                'processed' => $processedCount,
                'completed' => $completedCount,
                'failed' => $failedCount
            ];

        } finally {
            $activeProcesses = $this->cache->get('active_processes') ?: [];
            if (is_array($activeProcesses)) {
                $currentPid = getmypid();
                $activeProcesses = array_filter($activeProcesses, function($pid) use ($currentPid) {
                    return $pid !== $currentPid && $pid > 0 && $this->isPidRunning($pid);
                });
                $this->cache->set('active_processes', $activeProcesses, 300);
            }
        }
    }

    /**
     * Trigger queue processor in a separate background command line process immediately
     */
    private function triggerQueueProcessingAsync(): void {
        if (getenv('GPS_TESTING') === '1') {
            return;
        }
        $occPath = \OC::$SERVERROOT . '/occ';
        if (file_exists($occPath)) {
            $cmd = "php " . escapeshellarg($occPath) . " group-photo-sorter:process-queue > /dev/null 2>&1 &";
            shell_exec($cmd);
        }
    }

    /**
     * Check if a process ID is running on Linux
     */
    private function isPidRunning(int $pid): bool {
        if (file_exists("/proc/$pid")) {
            return true;
        }
        $output = [];
        $returnVal = -1;
        @exec("ps -p " . $pid, $output, $returnVal);
        return $returnVal === 0;
    }

    /**
     * Terminate a running process ID
     */
    private function killPid(int $pid): void {
        @exec("kill -9 " . $pid);
    }

    /**
     * Start video conversion in background using FFmpeg
     */
    private function startVideoConversion(ConversionTask $task, int $crf): bool {
        $logPath = $task->getTempPath() . '.log';
        
        // H.264 + AAC optimization
        $cmd = "ffmpeg -i " . escapeshellarg($task->getTempPath()) . 
               " -c:v libx264 -preset medium -crf " . escapeshellarg($crf) . 
               " -c:a aac -b:a 128k -movflags +faststart -y " . 
               escapeshellarg($task->getOutputPath()) . 
               " > " . escapeshellarg($logPath) . " 2>&1 & echo $!";

        $pid = (int)trim(shell_exec($cmd));

        if ($pid > 0) {
            $task->setStatus('processing');
            $task->setPid($pid);
            $task->setUpdatedAt(new \DateTime());
            $this->taskMapper->updateTask($task);
            return true;
        } else {
            $this->markTaskFailed($task, 'Failed to launch FFmpeg process');
            return false;
        }
    }

    /**
     * Start image conversion synchronously (inside the background runner thread)
     */
    private function startImageConversion(ConversionTask $task, int $quality): bool {
        $converterScript = __DIR__ . '/../../bin/converter.py';
        $pythonBin = __DIR__ . '/../../venv/bin/python3';
        if (!file_exists($pythonBin)) {
            $pythonBin = __DIR__ . '/../../.venv/bin/python3';
            if (!file_exists($pythonBin)) {
                $pythonBin = 'python3';
            }
        }
        
        $cmd = escapeshellarg($pythonBin) . " " . escapeshellarg($converterScript) . " convert-image " . 
               escapeshellarg($task->getTempPath()) . " " . 
               escapeshellarg($task->getOutputPath()) . " " . 
               escapeshellarg($quality);

        $output = [];
        $returnVal = -1;
        @exec($cmd, $output, $returnVal);

        if ($returnVal === 0 && file_exists($task->getOutputPath()) && filesize($task->getOutputPath()) > 0) {
            $this->finalizeTaskSuccess($task);
            return true;
        } else {
            $errorMsg = implode("\n", $output);
            if (empty($errorMsg)) {
                $errorMsg = "Python converter script failed";
            }
            $this->markTaskFailed($task, $errorMsg);
            return false;
        }
    }

    /**
     * Mark a task as failed and clean up files
     */
    private function markTaskFailed(ConversionTask $task, string $errorMessage): void {
        $task->setStatus('failed');
        $task->setErrorMessage($errorMessage);
        $task->setUpdatedAt(new \DateTime());
        $this->taskMapper->updateTask($task);

        // Delete temp files
        $this->cleanupTempFiles($task);
    }

    /**
     * Complete a task: extract metadata, upload, record statistics
     */
    private function finalizeTaskSuccess(ConversionTask $task): void {
        try {
            $folder = $this->folderMapper->find($task->getFolderId());

            // 1. Read metadata (date and dimensions)
            $metadata = $this->extractMetadata($task->getTempPath());
            $creationDate = isset($metadata['creation_date']) ? new \DateTime($metadata['creation_date']) : null;

            // Deciding extension and checking type
            $ext = strtolower(pathinfo($task->getOriginalFilename(), PATHINFO_EXTENSION));
            $videoExts = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'hevc', 'm4v', 'wmv', 'flv', '3gp'];
            $isVideo = in_array($ext, $videoExts, true);

            // 2. Generate unique filename
            $newFilename = $this->storageService->generateFilename(
                $folder,
                $task->getOriginalFilename(),
                $creationDate,
                $isVideo
            );
            $uniqueFilename = $this->storageService->getUniqueFilename(
                $folder->getOwnerId(),
                $folder->getNextcloudFolderPath(),
                $newFilename
            );

            // 3. Streaming Upload to Nextcloud Virtual Filesystem
            $remotePath = $folder->getNextcloudFolderPath() . '/' . $uniqueFilename;
            $mtime = $creationDate ? $creationDate->getTimestamp() : null;
            
            $this->storageService->writeToFolderStreaming(
                $folder->getOwnerId(),
                $remotePath,
                $task->getOutputPath(),
                $mtime
            );

            // 4. Record statistics
            $stats = new UploadStats();
            $stats->setFolderId($folder->getId());
            $stats->setUploaderIp($_SERVER['REMOTE_ADDR'] ?? '127.0.0.1');
            $stats->setFilenameOriginal($task->getOriginalFilename());
            $stats->setFilenameConverted($uniqueFilename);
            $stats->setFileSizeOriginal(filesize($task->getTempPath()));
            $stats->setFileSizeConverted(filesize($task->getOutputPath()));
            $stats->setFileType($isVideo ? 'video' : 'image');
            
            $timeDiff = time() - $task->getCreatedAt()->getTimestamp();
            $stats->setConversionTimeSeconds((double)$timeDiff);
            $stats->setUploadedAt(new \DateTime());
            $this->statsMapper->insert($stats);

            // 5. Update task state
            $task->setStatus('completed');
            $task->setUpdatedAt(new \DateTime());
            $this->taskMapper->updateTask($task);

        } catch (\Exception $e) {
            $this->markTaskFailed($task, 'Finalization error: ' . $e->getMessage());
            return;
        }

        // Clean up temp files
        $this->cleanupTempFiles($task);
    }

    /**
     * Extract metadata using python helper
     */
    private function extractMetadata(string $path): array {
        $converterScript = __DIR__ . '/../../bin/converter.py';
        $pythonBin = __DIR__ . '/../../venv/bin/python3';
        if (!file_exists($pythonBin)) {
            $pythonBin = __DIR__ . '/../../.venv/bin/python3';
            if (!file_exists($pythonBin)) {
                $pythonBin = 'python3';
            }
        }
        
        $cmd = escapeshellarg($pythonBin) . " " . escapeshellarg($converterScript) . " metadata " . escapeshellarg($path);
        
        $output = [];
        $returnVal = -1;
        @exec($cmd, $output, $returnVal);

        if ($returnVal === 0 && !empty($output)) {
            $decoded = json_decode($output[0], true);
            if (is_array($decoded)) {
                return $decoded;
            }
        }
        return [];
    }

    /**
     * Delete files associated with a task
     */
    private function cleanupTempFiles(ConversionTask $task): void {
        if (file_exists($task->getTempPath())) {
            @unlink($task->getTempPath());
        }
        if (file_exists($task->getOutputPath())) {
            @unlink($task->getOutputPath());
        }
        $logPath = $task->getTempPath() . '.log';
        if (file_exists($logPath)) {
            @unlink($logPath);
        }
    }
}
