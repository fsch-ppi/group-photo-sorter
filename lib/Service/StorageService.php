<?php

namespace OCA\GroupPhotoSorter\Service;

use OCP\Files\IRootFolder;
use OCP\Files\Folder as NCFolder;
use OCP\Files\File as NCFile;
use OCP\Share\IManager as ShareManager;
use OCP\Share\IShare;
use OCA\GroupPhotoSorter\Db\Folder;

class StorageService {

    private IRootFolder $rootFolder;
    private ShareManager $shareManager;

    public function __construct(IRootFolder $rootFolder, ShareManager $shareManager) {
        $this->rootFolder = $rootFolder;
        $this->shareManager = $shareManager;
    }

    /**
     * Get user's root folder
     */
    private function getUserFolder(string $userId): NCFolder {
        return $this->rootFolder->getUserFolder($userId);
    }

    /**
     * Create folder path recursively if it doesn't exist
     */
    public function createFolder(string $userId, string $path): void {
        $userFolder = $this->getUserFolder($userId);
        $parts = explode('/', trim($path, '/'));
        $currentFolder = $userFolder;

        foreach ($parts as $part) {
            if ($part === '') {
                continue;
            }
            if (!$currentFolder->nodeExists($part)) {
                $currentFolder = $currentFolder->newFolder($part);
            } else {
                $node = $currentFolder->get($part);
                if ($node instanceof NCFolder) {
                    $currentFolder = $node;
                } else {
                    throw new \RuntimeException("Path component '$part' exists but is a file, not a folder");
                }
            }
        }
    }

    /**
     * Check if a file or folder exists
     */
    public function fileExists(string $userId, string $path): bool {
        $userFolder = $this->getUserFolder($userId);
        return $userFolder->nodeExists(trim($path, '/'));
    }

    /**
     * Write file content (in-memory)
     */
    public function writeToFolder(string $userId, string $path, string $content, ?int $mtime = null): NCFile {
        $userFolder = $this->getUserFolder($userId);
        $path = trim($path, '/');
        $parentPath = dirname($path);
        $filename = basename($path);

        $this->createFolder($userId, $parentPath);
        $folder = $parentPath === '.' ? $userFolder : $userFolder->get($parentPath);

        if ($folder->nodeExists($filename)) {
            $file = $folder->get($filename);
            if (!($file instanceof NCFile)) {
                throw new \RuntimeException("Cannot overwrite: target path exists and is a directory");
            }
        } else {
            $file = $folder->newFile($filename);
        }

        $file->putContent($content);

        if ($mtime !== null) {
            $file->touch($mtime);
        }

        return $file;
    }

    /**
     * Write file from local temporary path (memory-efficient streaming)
     */
    public function writeToFolderStreaming(string $userId, string $path, string $tempFilePath, ?int $mtime = null): NCFile {
        $userFolder = $this->getUserFolder($userId);
        $path = trim($path, '/');
        $parentPath = dirname($path);
        $filename = basename($path);

        $this->createFolder($userId, $parentPath);
        $folder = $parentPath === '.' ? $userFolder : $userFolder->get($parentPath);

        if ($folder->nodeExists($filename)) {
            $file = $folder->get($filename);
            if (!($file instanceof NCFile)) {
                throw new \RuntimeException("Cannot overwrite: target path exists and is a directory");
            }
        } else {
            $file = $folder->newFile($filename);
        }

        // Open read stream from local temp file
        $readStream = fopen($tempFilePath, 'r');
        if ($readStream === false) {
            throw new \RuntimeException("Could not read temporary file: " . $tempFilePath);
        }

        try {
            $file->putContent($readStream);
        } finally {
            if (is_resource($readStream)) {
                fclose($readStream);
            }
        }

        if ($mtime !== null) {
            $file->touch($mtime);
        }

        return $file;
    }

    /**
     * Create a public share link for a folder
     */
    public function createShareLink(string $userId, string $path): string {
        $userFolder = $this->getUserFolder($userId);
        $node = $userFolder->get(trim($path, '/'));

        // Check if share already exists
        $shares = $this->shareManager->getSharesByPath($node);
        foreach ($shares as $share) {
            if ($share->getShareType() === IShare::TYPE_LINK) {
                return $share->getToken();
            }
        }

        // Create new link share
        $newShare = $this->shareManager->newShare();
        $newShare->setNode($node)
                 ->setShareType(IShare::TYPE_LINK)
                 ->setPermissions(\OCP\Constants::PERMISSION_READ)
                 ->setSharedBy($userId);

        $createdShare = $this->shareManager->createShare($newShare);
        return $createdShare->getToken();
    }

    /**
     * Delete/revoke public share links for a folder path
     */
    public function deleteShareLink(string $userId, string $path): void {
        $userFolder = $this->getUserFolder($userId);
        $trimmedPath = trim($path, '/');
        
        if (!$userFolder->nodeExists($trimmedPath)) {
            return;
        }

        $node = $userFolder->get($trimmedPath);
        $shares = $this->shareManager->getSharesByPath($node);
        foreach ($shares as $share) {
            if ($share->getShareType() === IShare::TYPE_LINK) {
                $this->shareManager->deleteShare($share);
            }
        }
    }

    /**
     * Generate name based on folder naming format
     */
    public function generateFilename(Folder $folder, string $originalFilename, ?\DateTime $fileDate, bool $isVideo): string {
        $dt = $fileDate ?? new \DateTime();

        $dateFull = $dt->format('Y-m-d_His');
        $dateDay = $dt->format('Y-m-d');
        $dateHour = $dt->format('Y-m-d_H');

        $ext = $isVideo ? '.mp4' : '.jpg';
        $event = str_replace(' ', '_', $folder->getEventName());
        $namingFormat = $folder->getNamingFormat();

        switch ($namingFormat) {
            case 'DATE_EVENT':
                $base = "{$dateFull}_{$event}";
                break;
            case 'EVENT_DATE':
                $base = "{$event}_{$dateFull}";
                break;
            case 'DATE_ONLY':
                $base = $dateFull;
                break;
            case 'DATE_DAY_ONLY':
                $base = $dateDay;
                break;
            case 'DATE_DAY_EVENT':
                $base = "{$dateDay}_{$event}";
                break;
            case 'EVENT_DATE_DAY':
                $base = "{$event}_{$dateDay}";
                break;
            case 'DATE_HOUR_EVENT':
                $base = "{$dateHour}_{$event}";
                break;
            case 'EVENT_DATE_HOUR':
                $base = "{$event}_{$dateHour}";
                break;
            default:
                $base = pathinfo($originalFilename, PATHINFO_FILENAME);
                break;
        }

        // Clean base string of any unsafe filename characters
        $base = preg_replace('/[^a-zA-Z0-9_\-]/', '_', $base);

        return $base . $ext;
    }

    /**
     * Get a unique filename in the given directory path
     */
    public function getUniqueFilename(string $userId, string $folderPath, string $filename): string {
        $userFolder = $this->getUserFolder($userId);
        $folderPath = trim($folderPath, '/');
        
        if (!$userFolder->nodeExists($folderPath)) {
            return $filename;
        }

        $folder = $userFolder->get($folderPath);
        if (!$folder->nodeExists($filename)) {
            return $filename;
        }

        $stem = pathinfo($filename, PATHINFO_FILENAME);
        $ext = pathinfo($filename, PATHINFO_EXTENSION);
        $ext = $ext ? '.' . $ext : '';

        $counter = 1;
        while ($counter <= 9999) {
            $newFilename = "{$stem}_{$counter}{$ext}";
            if (!$folder->nodeExists($newFilename)) {
                return $newFilename;
            }
            $counter++;
        }

        throw new \RuntimeException("Too many filename conflicts in Nextcloud folder");
    }
}
