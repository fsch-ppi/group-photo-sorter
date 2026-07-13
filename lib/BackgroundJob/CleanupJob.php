<?php

namespace OCA\GroupPhotoSorter\BackgroundJob;

use OCP\BackgroundJob\TimedJob;
use OCP\AppFramework\Utility\ITimeFactory;
use OCA\GroupPhotoSorter\Db\UploadStatsMapper;
use OCA\GroupPhotoSorter\Db\ConversionTaskMapper;

class CleanupJob extends TimedJob {

    private UploadStatsMapper $statsMapper;
    private ConversionTaskMapper $taskMapper;

    public function __construct(
        ITimeFactory $timeFactory, 
        UploadStatsMapper $statsMapper,
        ConversionTaskMapper $taskMapper
    ) {
        parent::__construct($timeFactory);
        $this->statsMapper = $statsMapper;
        $this->taskMapper = $taskMapper;
        // Run daily (86400 seconds)
        $this->setInterval(86400);
    }

    /**
     * Run the maintenance operations
     */
    protected function run($argument): void {
        // 1. GDPR: Anonymize IP addresses older than 30 days
        $cutoffDate = new \DateTime('-30 days');
        $this->statsMapper->anonymizeOldIps($cutoffDate);

        // 2. Clean up old conversion tasks
        try {
            // Completed or failed tasks older than 2 hours
            $taskCutoff = new \DateTime('-2 hours');
            $this->taskMapper->deleteTasksOlderThan($taskCutoff, ['completed', 'failed']);
            
            // Stuck pending/processing tasks older than 24 hours
            $stuckCutoff = new \DateTime('-24 hours');
            $this->taskMapper->deleteTasksOlderThan($stuckCutoff);
        } catch (\Exception $e) {
            // Ignore DB errors to ensure file cleanup still runs
        }

        // 3. Clean up orphaned temp files older than 24 hours
        $tempDir = sys_get_temp_dir() . '/gps_uploads';
        if (file_exists($tempDir) && is_dir($tempDir)) {
            $files = glob($tempDir . '/*');
            $now = time();
            $maxAge = 86400; // 24 hours in seconds

            foreach ($files as $file) {
                if (is_file($file)) {
                    if ($now - filemtime($file) > $maxAge) {
                        @unlink($file);
                    }
                }
            }
        }
    }
}
