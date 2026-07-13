<?php

namespace OCA\GroupPhotoSorter\Db;

use OCP\AppFramework\Db\Entity;

class UploadStats extends Entity implements \JsonSerializable {

    protected $folderId;
    protected $uploaderIp;
    protected $filenameOriginal;
    protected $filenameConverted;
    protected $fileSizeOriginal;
    protected $fileSizeConverted;
    protected $fileType;
    protected $conversionTimeSeconds;
    protected $uploadedAt;

    public function __construct() {
        $this->addType('id', 'integer');
        $this->addType('folderId', 'integer');
        $this->addType('fileSizeOriginal', 'integer');
        $this->addType('fileSizeConverted', 'integer');
        $this->addType('conversionTimeSeconds', 'double');
        $this->addType('uploadedAt', 'datetime');
    }

    public function jsonSerialize(): array {
        return [
            'id' => $this->getId(),
            'folder_id' => $this->getFolderId(),
            'uploader_ip' => $this->getUploaderIp(),
            'filename_original' => $this->getFilenameOriginal(),
            'filename_converted' => $this->getFilenameConverted(),
            'file_size_original' => $this->getFileSizeOriginal(),
            'file_size_converted' => $this->getFileSizeConverted(),
            'file_type' => $this->getFileType(),
            'conversion_time_seconds' => $this->getConversionTimeSeconds(),
            'uploaded_at' => $this->getUploadedAt() ? $this->getUploadedAt()->format(\DateTimeInterface::ATOM) : null,
        ];
    }
}
