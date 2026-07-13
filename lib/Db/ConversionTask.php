<?php

namespace OCA\GroupPhotoSorter\Db;

use OCP\AppFramework\Db\Entity;

class ConversionTask extends Entity implements \JsonSerializable {

    protected $folderId;
    protected $status;
    protected $pid;
    protected $originalFilename;
    protected $tempPath;
    protected $outputPath;
    protected $errorMessage;
    protected $createdAt;
    protected $updatedAt;

    public function __construct() {
        $this->addType('id', 'string');
        $this->addType('folderId', 'integer');
        $this->addType('pid', 'integer');
        $this->addType('createdAt', 'datetime');
        $this->addType('updatedAt', 'datetime');
    }

    public function jsonSerialize(): array {
        return [
            'task_id' => $this->getId(),
            'folder_id' => $this->getFolderId(),
            'status' => $this->getStatus(),
            'pid' => $this->getPid(),
            'original_filename' => $this->getOriginalFilename(),
            'temp_path' => $this->getTempPath(),
            'output_path' => $this->getOutputPath(),
            'error' => $this->getErrorMessage(),
            'created_at' => $this->getCreatedAt() ? $this->getCreatedAt()->format(\DateTimeInterface::ATOM) : null,
            'updated_at' => $this->getUpdatedAt() ? $this->getUpdatedAt()->format(\DateTimeInterface::ATOM) : null,
        ];
    }
}
