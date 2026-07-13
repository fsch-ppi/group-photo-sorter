<?php

namespace OCA\GroupPhotoSorter\Db;

use OCP\AppFramework\Db\Entity;

class Folder extends Entity implements \JsonSerializable {

    protected $ownerId;
    protected $displayName;
    protected $eventName;
    protected $nextcloudFolderPath;
    protected $namingFormat;
    protected $jpegQuality;
    protected $videoCrf;
    protected $token;
    protected $ncShareToken;
    protected $readmeMessage;
    protected $createdAt;
    protected $isActive;
    public $uploadCount = null;

    public function __construct() {
        $this->addType('id', 'integer');
        $this->addType('jpegQuality', 'integer');
        $this->addType('videoCrf', 'integer');
        $this->addType('isActive', 'boolean');
        $this->addType('createdAt', 'datetime');
    }

    public function getUploadCount(): ?int {
        return $this->uploadCount;
    }

    public function setUploadCount(?int $uploadCount): void {
        $this->uploadCount = $uploadCount;
    }

    public function getIsActive(): bool {
        return $this->isActive !== null ? (bool)$this->isActive : true;
    }

    public function setIsActive(bool $isActive): void {
        $this->isActive = $isActive;
        $this->markFieldUpdated('isActive');
    }

    public function jsonSerialize(): array {
        $urlGenerator = \OC::$server->getURLGenerator();
        $uploadUrl = $urlGenerator->getAbsoluteURL(
            $urlGenerator->linkToRoute('group_photo_sorter.page.uploadPage', ['token' => $this->getToken()])
        );
        $ncShareUrl = null;
        if ($this->getNcShareToken()) {
            $ncShareUrl = $urlGenerator->getAbsoluteURL('/s/' . $this->getNcShareToken());
        }

        return [
            'id' => $this->getId(),
            'owner_id' => $this->getOwnerId(),
            'name' => $this->getDisplayName(),
            'event_name' => $this->getEventName(),
            'nextcloud_folder_path' => $this->getNextcloudFolderPath(),
            'naming_format' => $this->getNamingFormat(),
            'jpeg_quality' => $this->getJpegQuality(),
            'video_crf' => $this->getVideoCrf(),
            'share_token' => $this->getToken(),
            'nextcloud_share_token' => $this->getNcShareToken(),
            'readme_message' => $this->getReadmeMessage(),
            'is_active' => $this->getIsActive(),
            'created_at' => $this->getCreatedAt() ? $this->getCreatedAt()->format(\DateTimeInterface::ATOM) : null,
            'upload_count' => $this->getUploadCount(),
            'upload_url' => $uploadUrl,
            'nextcloud_share_url' => $ncShareUrl,
        ];
    }
}
