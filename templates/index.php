<?php
/**
 * Admin Dashboard Template for group_photo_sorter app
 */

// Add CSS and JS compiled bundles
\OCP\Util::addStyle('group_photo_sorter', 'group_photo_sorter');
\OCP\Util::addScript('group_photo_sorter', 'group_photo_sorter');

$urlGenerator = \OC::$server->getURLGenerator();
$apiBase = rtrim($urlGenerator->linkToRoute('group_photo_sorter.page.index'), '/');
?>

<div id="group-photo-sorter-admin" class="gps-app" data-api-base="<?php p($apiBase); ?>">
    <div class="loading-spinner">Loading Group Photo Sorter...</div>
</div>

