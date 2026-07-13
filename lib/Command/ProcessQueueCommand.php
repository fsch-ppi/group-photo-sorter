<?php

namespace OCA\GroupPhotoSorter\Command;

use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;
use OCA\GroupPhotoSorter\Service\ConversionService;

class ProcessQueueCommand extends Command {

    private ConversionService $conversionService;

    public function __construct(ConversionService $conversionService) {
        parent::__construct();
        $this->conversionService = $conversionService;
    }

    protected function configure(): void {
        $this->setName('group-photo-sorter:process-queue')
             ->setDescription('Process pending image and video conversions');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int {
        $output->writeln("Processing group photo sorter conversion queue...");
        $result = $this->conversionService->processQueue();
        
        if (isset($result['status']) && $result['status'] === 'locked') {
            $output->writeln("Queue is locked: " . $result['message']);
            return Command::SUCCESS;
        }

        $output->writeln("Queue run completed:");
        $output->writeln("- Processed: " . $result['processed']);
        $output->writeln("- Completed: " . $result['completed']);
        $output->writeln("- Failed: " . $result['failed']);

        return Command::SUCCESS;
    }
}
