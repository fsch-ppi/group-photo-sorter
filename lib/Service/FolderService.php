<?php

namespace OCA\GroupPhotoSorter\Service;

use OCP\Security\ISecureRandom;
use OCP\AppFramework\Db\DoesNotExistException;
use OCA\GroupPhotoSorter\Db\Folder;
use OCA\GroupPhotoSorter\Db\FolderMapper;
use OCA\GroupPhotoSorter\Db\UploadStatsMapper;

class FolderService {

    private FolderMapper $mapper;
    private UploadStatsMapper $statsMapper;
    private StorageService $storageService;
    private ISecureRandom $random;

    public function __construct(
        FolderMapper $mapper,
        UploadStatsMapper $statsMapper,
        StorageService $storageService,
        ISecureRandom $random
    ) {
        $this->mapper = $mapper;
        $this->statsMapper = $statsMapper;
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

        return $this->mapper->insert($folder);
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

        return $this->mapper->update($folder);
    }

    /**
     * Delete folder settings
     */
    public function delete(int $id, string $ownerId): void {
        $folder = $this->get($id, $ownerId);
        
        // Revoke the Nextcloud share link if it exists
        if ($folder->getNcShareToken()) {
            try {
                $this->storageService->deleteShareLink($ownerId, $folder->getNextcloudFolderPath());
            } catch (\Exception $e) {
                // Log and ignore to make sure database entry deletion proceeds
            }
        }
        
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
