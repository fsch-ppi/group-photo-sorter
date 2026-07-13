<?php

namespace OCA\GroupPhotoSorter\AppInfo;

use OCP\AppFramework\App;
use OCP\AppFramework\Bootstrap\IBootstrap;
use OCP\AppFramework\Bootstrap\IBootContext;
use OCP\AppFramework\Bootstrap\IRegistrationContext;
use OCA\GroupPhotoSorter\Controller\PageController;
use OCA\GroupPhotoSorter\Controller\FolderApiController;
use OCA\GroupPhotoSorter\Controller\UploadApiController;
use OCA\GroupPhotoSorter\Db\FolderMapper;
use OCA\GroupPhotoSorter\Db\UploadStatsMapper;
use OCA\GroupPhotoSorter\Db\ConversionTaskMapper;
use OCA\GroupPhotoSorter\Service\FolderService;
use OCA\GroupPhotoSorter\Service\ConversionService;
use OCA\GroupPhotoSorter\Service\StorageService;
use OCA\GroupPhotoSorter\Command\ProcessQueueCommand;

class Application extends App implements IBootstrap {

    public const APP_ID = 'group_photo_sorter';

    public function __construct(array $urlParams = []) {
        parent::__construct(self::APP_ID, $urlParams);
    }

    public function register(IRegistrationContext $context): void {
        // Register other services if needed
    }

    public function boot(IBootContext $context): void {
        // Run code on app load
    }
}
