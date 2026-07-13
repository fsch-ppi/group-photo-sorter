<?php

namespace OCA\GroupPhotoSorter\BackgroundJob;

use OCP\BackgroundJob\TimedJob;
use OCP\AppFramework\Utility\ITimeFactory;
use OCA\GroupPhotoSorter\Service\ConversionService;

class ConversionJob extends TimedJob {

    private ConversionService $conversionService;

    public function __construct(ITimeFactory $timeFactory, ConversionService $conversionService) {
        parent::__construct($timeFactory);
        $this->conversionService = $conversionService;
        // Run every minute
        $this->setInterval(60);
    }

    /**
     * Run the background job
     */
    protected function run($argument): void {
        $this->conversionService->processQueue();
    }
}
