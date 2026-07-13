<?php
/**
 * Public Guest Upload Template for group_photo_sorter app
 */

// Add CSS and JS compiled bundles
\OCP\Util::addStyle('group_photo_sorter', 'group_photo_sorter');
\OCP\Util::addScript('group_photo_sorter', 'group_photo_sorter');

$urlGenerator = \OC::$server->getURLGenerator();
$apiBase = rtrim($urlGenerator->linkToRoute('group_photo_sorter.page.index'), '/');
?>

<div id="group-photo-sorter-upload" class="gps-app" data-api-base="<?php p($apiBase); ?>" data-token="<?php p($_['token']); ?>">
    <div class="loading-spinner">Preparing upload area...</div>
</div>

