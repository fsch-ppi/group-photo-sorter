<?php
require_once '/var/www/html/lib/base.php';

$container = \OC::$server->getRegisteredAppContainer('group_photo_sorter');
$mapper = $container->query(\OCA\GroupPhotoSorter\Db\ConversionTaskMapper::class);

echo "findPending():\n";
foreach ($mapper->findPending() as $task) {
    echo "Task ID: " . $task->getId() . ", Status: " . $task->getStatus() . "\n";
}

echo "\nfindProcessing():\n";
foreach ($mapper->findProcessing() as $task) {
    echo "Task ID: " . $task->getId() . ", Status: " . $task->getStatus() . "\n";
}
