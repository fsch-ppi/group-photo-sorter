<?php
/**
 * Routing configuration for group_photo_sorter app
 */

return [
    'routes' => [
        // Page Views
        ['name' => 'Page#index', 'url' => '/', 'verb' => 'GET'],
        ['name' => 'Page#uploadPage', 'url' => '/upload/{token}', 'verb' => 'GET'],

        // Folder Administration API (Authenticated Admin only)
        ['name' => 'FolderApi#index', 'url' => '/api/v1/folders/', 'verb' => 'GET'],
        ['name' => 'FolderApi#create', 'url' => '/api/v1/folders/', 'verb' => 'POST'],
        ['name' => 'FolderApi#namingFormats', 'url' => '/api/v1/folders/naming_formats/', 'verb' => 'GET'],
        ['name' => 'FolderApi#show', 'url' => '/api/v1/folders/{id}/', 'verb' => 'GET'],
        ['name' => 'FolderApi#update', 'url' => '/api/v1/folders/{id}/', 'verb' => 'PATCH'],
        ['name' => 'FolderApi#destroy', 'url' => '/api/v1/folders/{id}/', 'verb' => 'DELETE'],
        ['name' => 'FolderApi#regenerateToken', 'url' => '/api/v1/folders/{id}/regenerate_token/', 'verb' => 'POST'],
        ['name' => 'FolderApi#regenerateNextcloudShare', 'url' => '/api/v1/folders/{id}/regenerate_nextcloud_share/', 'verb' => 'POST'],
        ['name' => 'FolderApi#statistics', 'url' => '/api/v1/folders/{id}/statistics/', 'verb' => 'GET'],

        // Public Upload API (Guest access)
        ['name' => 'UploadApi#info', 'url' => '/api/v1/upload/{token}/info/', 'verb' => 'GET'],
        ['name' => 'UploadApi#upload', 'url' => '/api/v1/upload/{token}/', 'verb' => 'POST'],
        ['name' => 'UploadApi#taskStatus', 'url' => '/api/v1/upload/task/{taskId}/', 'verb' => 'GET'],
    ]
];
