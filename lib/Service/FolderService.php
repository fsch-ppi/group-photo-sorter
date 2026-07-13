<?php

namespace OCA\GroupPhotoSorter\Service;

use OCP\Security\ISecureRandom;
use OCP\AppFramework\Db\DoesNotExistException;
use OCA\GroupPhotoSorter\Db\Folder;
use OCA\GroupPhotoSorter\Db\FolderMapper;
use OCA\GroupPhotoSorter\Db\UploadStatsMapper;
use OCA\GroupPhotoSorter\Db\ConversionTaskMapper;

class FolderService {

    private FolderMapper $mapper;
    private UploadStatsMapper $statsMapper;
    private ConversionTaskMapper $taskMapper;
    private StorageService $storageService;
    private ISecureRandom $random;

    public function __construct(
        FolderMapper $mapper,
        UploadStatsMapper $statsMapper,
        ConversionTaskMapper $taskMapper,
        StorageService $storageService,
        ISecureRandom $random
    ) {
        $this->mapper = $mapper;
        $this->statsMapper = $statsMapper;
        $this->taskMapper = $taskMapper;
        $this->storageService = $storageService;
        $this->random = $random;
    }


    /**
     * List all folders for a user
     * @return Folder[]
     */
    public function list(string $ownerId): array {
        $folders = $this->mapper->findByOwner($ownerId);
        foreach ($folders as $folder) {
            $folder->setUploadCount($this->statsMapper->getUploadCount($folder->getId()));
        }
        return $folders;
    }

    /**
     * Get a folder by ID, checking ownership
     */
    public function get(int $id, string $ownerId): Folder {
        $folder = $this->mapper->find($id);
        if ($folder->getOwnerId() !== $ownerId) {
            throw new \UnauthorizedException("You do not own this folder");
        }
        $folder->setUploadCount($this->statsMapper->getUploadCount($folder->getId()));
        return $folder;
    }

    /**
     * Create a new folder
     */
    public function create(string $ownerId, array $data): Folder {
        $displayName = $data['name'] ?? 'New Folder';
        $eventName = $data['event_name'] ?? 'event';
        $path = $data['nextcloud_folder_path'] ?? 'Photos/' . $eventName;
        $namingFormat = $data['naming_format'] ?? 'DATE_EVENT';
        $jpegQuality = isset($data['jpeg_quality']) ? (int)$data['jpeg_quality'] : 90;
        $videoCrf = isset($data['video_crf']) ? (int)$data['video_crf'] : 23;
        $readmeMessage = $data['readme_message'] ?? null;

        // 1. Create the physical Nextcloud directory
        $this->storageService->createFolder($ownerId, $path);

        // 2. Create the Nextcloud share link for the folder
        $ncShareToken = null;
        try {
            $ncShareToken = $this->storageService->createShareLink($ownerId, $path);
        } catch (\Exception $e) {
            // Log warning but continue; share link can be created later
        }

        // 3. Generate upload token
        $token = $this->random->generate(32, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789');

        $folder = new Folder();
        $folder->setOwnerId($ownerId);
        $folder->setDisplayName($displayName);
        $folder->setEventName($eventName);
        $folder->setNextcloudFolderPath($path);
        $folder->setNamingFormat($namingFormat);
        $folder->setJpegQuality($jpegQuality);
        $folder->setVideoCrf($videoCrf);
        $folder->setToken($token);
        $folder->setNcShareToken($ncShareToken);
        $folder->setReadmeMessage($readmeMessage);
        $folder->setIsActive(true);
        $folder->setCreatedAt(new \DateTime());

        $inserted = $this->mapper->insert($folder);
        $this->writeReadmeFile($inserted);
        return $inserted;
    }

    /**
     * Update an existing folder
     */
    public function update(int $id, string $ownerId, array $data): Folder {
        $folder = $this->get($id, $ownerId);

        if (isset($data['name'])) {
            $folder->setDisplayName($data['name']);
        }
        if (isset($data['event_name'])) {
            $folder->setEventName($data['event_name']);
        }
        if (isset($data['naming_format'])) {
            $folder->setNamingFormat($data['naming_format']);
        }
        if (isset($data['jpeg_quality'])) {
            $folder->setJpegQuality((int)$data['jpeg_quality']);
        }
        if (isset($data['video_crf'])) {
            $folder->setVideoCrf((int)$data['video_crf']);
        }
        if (array_key_exists('readme_message', $data)) {
            $folder->setReadmeMessage($data['readme_message']);
        }
        if (isset($data['is_active'])) {
            $folder->setIsActive((bool)$data['is_active']);
        }

        $updated = $this->mapper->update($folder);
        $this->writeReadmeFile($updated);
        return $updated;
    }

    /**
     * Create or update README.md in the target Nextcloud folder
     */
    private function writeReadmeFile(Folder $folder): void {
        try {
            $urlGenerator = \OC::$server->getURLGenerator();
            $uploadUrl = $urlGenerator->getAbsoluteURL($urlGenerator->linkToRoute('group_photo_sorter.page.uploadPage', ['token' => $folder->getToken()]));
            
            $content = "# Photo Import Sorter\n\n" .
                "This folder is configured to receive and automatically sort photos and videos for the event:\n" .
                "### **" . $folder->getDisplayName() . "** (Event tag: `" . $folder->getEventName() . "`)\n\n" .
                "## Guest Upload Link\n" .
                "Share this link with guests so they can upload photos and videos directly from their mobile phones or browsers:\n" .
                "👉 **[" . $uploadUrl . "](" . $uploadUrl . ")**\n\n" .
                "## Folder Configuration\n" .
                "- **Naming Format**: `" . $folder->getNamingFormat() . "`\n" .
                "- **JPEG Quality**: " . $folder->getJpegQuality() . "%\n" .
                "- **Video Compression**: CRF " . $folder->getVideoCrf() . "\n" .
                "- **Created At**: " . $folder->getCreatedAt()->format('Y-m-d H:i:s') . "\n";
                
            if ($folder->getReadmeMessage()) {
                $content .= "\n## Welcome Message / Instructions\n" .
                    $folder->getReadmeMessage() . "\n";
            }
            
            $content .= "\n---\n" .
                "*Automatically generated by the Nextcloud Photo Import Sorter application.*\n";

            $this->storageService->writeToFolder(
                $folder->getOwnerId(),
                $folder->getNextcloudFolderPath() . '/README.md',
                $content
            );
        } catch (\Exception $e) {
            \OC::$server->getLogger()->warning(
                'Failed to create README.md file in folder: ' . $e->getMessage(),
                ['app' => 'group_photo_sorter']
            );
        }
    }

    /**
     * Delete folder settings
     */
    public function delete(int $id, string $ownerId): void {
        $folder = $this->get($id, $ownerId);
        
        if ($folder->getIsActive()) {
            throw new \Exception("Cannot delete an active folder configuration. Please pause it first.");
        }
        
        // Revoke the Nextcloud share link if it exists
        try {
            $this->storageService->deleteShareLink($ownerId, $folder->getNextcloudFolderPath());
        } catch (\Exception $e) {
            // Log and ignore to make sure database entry deletion proceeds
        }
        
        // Cascade delete associated statistics and conversion tasks
        $this->statsMapper->deleteForFolder($id);
        $this->taskMapper->deleteForFolder($id);
        
        $this->mapper->delete($folder);
    }

    /**
     * Regenerate public upload token
     */
    public function regenerateToken(int $id, string $ownerId): Folder {
        $folder = $this->get($id, $ownerId);
        $newToken = $this->random->generate(32, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789');
        $folder->setToken($newToken);
        return $this->mapper->update($folder);
    }

    /**
     * Regenerate Nextcloud share link
     */
    public function regenerateNextcloudShare(int $id, string $ownerId): Folder {
        $folder = $this->get($id, $ownerId);
        $ncShareToken = $this->storageService->createShareLink($ownerId, $folder->getNextcloudFolderPath());
        $folder->setNcShareToken($ncShareToken);
        return $this->mapper->update($folder);
    }
}
