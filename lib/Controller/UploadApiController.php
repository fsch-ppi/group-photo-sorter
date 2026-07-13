<?php

namespace OCA\GroupPhotoSorter\Controller;

use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\DataResponse;
use OCP\IRequest;
use OCP\AppFramework\Http;
use OCP\AppFramework\Db\DoesNotExistException;
use OCA\GroupPhotoSorter\Db\FolderMapper;
use OCA\GroupPhotoSorter\Service\ConversionService;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\PublicPage;
use OCP\ICacheFactory;
use OCP\ICache;

class UploadApiController extends Controller {

    private FolderMapper $folderMapper;
    private ConversionService $conversionService;
    private ICache $cache;

    public function __construct(
        string $appName,
        IRequest $request,
        FolderMapper $folderMapper,
        ConversionService $conversionService,
        ICacheFactory $cacheFactory
    ) {
        parent::__construct($appName, $request);
        $this->folderMapper = $folderMapper;
        $this->conversionService = $conversionService;
        $this->cache = $cacheFactory->createDistributed('group_photo_sorter');
    }

    /**
     * Get folder/event details for public upload page
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @PublicPage
     * @Guest
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    #[PublicPage]
    public function info(string $token): DataResponse {
        try {
            $folder = $this->folderMapper->findByToken($token);
            
            if (!$folder->getIsActive()) {
                return new DataResponse(['error' => 'This upload link is paused'], Http::STATUS_FORBIDDEN);
            }

            $shareUrl = null;
            if ($folder->getNcShareToken()) {
                $shareUrl = \OC::$server->getURLGenerator()->getAbsoluteURL(
                    '/s/' . $folder->getNcShareToken()
                );
            }

            $info = [
                'name' => $folder->getDisplayName(),
                'event_name' => $folder->getEventName(),
                'nextcloud_share_url' => $shareUrl,
                'readme_message' => $folder->getReadmeMessage(),
                'supported_image_formats' => ['png', 'jpg', 'jpeg', 'heic', 'heif', 'tiff', 'tif', 'cr2', 'nef', 'arw', 'dng', 'raw', 'webp', 'bmp', 'gif'],
                'supported_video_formats' => ['mp4', 'mov', 'avi', 'mkv', 'webm', 'hevc', 'm4v', 'wmv', 'flv', '3gp'],
                'max_upload_size_mb' => 5120 // 5GB limit
            ];

            return new DataResponse($info);
        } catch (DoesNotExistException $e) {
            return new DataResponse(['error' => 'Folder not found'], Http::STATUS_NOT_FOUND);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Upload a photo or video anonymously
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @PublicPage
     * @Guest
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    #[PublicPage]
    public function upload(string $token): DataResponse {
        try {
            $folder = $this->folderMapper->findByToken($token);

            if (!$folder->getIsActive()) {
                return new DataResponse(['error' => 'This upload link is paused'], Http::STATUS_FORBIDDEN);
            }

            // Fetch the uploaded file details
            $file = $this->request->getUploadedFile('file');
            if ($file === null || $file['error'] !== UPLOAD_ERR_OK) {
                return new DataResponse(['error' => 'No file uploaded or file upload error'], Http::STATUS_BAD_REQUEST);
            }

            $originalFilename = $file['name'];
            $tempUploadedPath = $file['tmp_name'];

            // Validate format
            $ext = strtolower(pathinfo($originalFilename, PATHINFO_EXTENSION));
            $supportedImages = ['png', 'jpg', 'jpeg', 'heic', 'heif', 'tiff', 'tif', 'cr2', 'nef', 'arw', 'dng', 'raw', 'webp', 'bmp', 'gif'];
            $supportedVideos = ['mp4', 'mov', 'avi', 'mkv', 'webm', 'hevc', 'm4v', 'wmv', 'flv', '3gp'];

            $isImage = in_array($ext, $supportedImages, true);
            $isVideo = in_array($ext, $supportedVideos, true);

            if (!$isImage && !$isVideo) {
                return new DataResponse(['error' => 'Unsupported file format'], Http::STATUS_BAD_REQUEST);
            }

            // Move to a permanent location in system temp folder for background worker to access
            $tempBaseDir = sys_get_temp_dir() . '/gps_uploads';
            if (!file_exists($tempBaseDir)) {
                mkdir($tempBaseDir, 0755, true);
            }

            $tempPath = $tempBaseDir . '/gps_in_' . bin2hex(random_bytes(16)) . '.' . $ext;
            if (!move_uploaded_file($tempUploadedPath, $tempPath)) {
                return new DataResponse(['error' => 'Failed to save uploaded file'], Http::STATUS_INTERNAL_SERVER_ERROR);
            }

            // Create a background conversion task
            $taskId = $this->conversionService->createTask(
                $folder->getId(),
                $tempPath,
                $originalFilename,
                $isVideo
            );

            // Record task in user session cache
            $sessionId = $this->request->getParam('session_id') ?: $this->request->getParam('sessionId');
            if ($sessionId) {
                $sessionKey = 'upload_session_' . $token . '_' . $sessionId;
                $sessionData = $this->cache->get($sessionKey);
                if ($sessionData !== null) {
                    $sessionData = json_decode($sessionData, true);
                }
                if (!is_array($sessionData)) {
                    $sessionData = [];
                }
                
                $sessionData[] = [
                    'taskId' => $taskId,
                    'name' => $originalFilename,
                    'size' => filesize($tempPath)
                ];
                
                $this->cache->set($sessionKey, json_encode($sessionData), 86400); // 24 hours
            }

            return new DataResponse([
                'success' => true,
                'task_id' => $taskId,
                'message' => 'File uploaded and queued for conversion'
            ]);

        } catch (DoesNotExistException $e) {
            return new DataResponse(['error' => 'Folder not found'], Http::STATUS_NOT_FOUND);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Get statuses of all tasks in the session
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @PublicPage
     * @Guest
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    #[PublicPage]
    public function sessionStatus(string $token, string $sessionId): DataResponse {
        try {
            $folder = $this->folderMapper->findByToken($token);

            if (!$folder->getIsActive()) {
                return new DataResponse(['error' => 'This upload link is paused'], Http::STATUS_FORBIDDEN);
            }

            $sessionKey = 'upload_session_' . $token . '_' . $sessionId;
            $sessionData = $this->cache->get($sessionKey);
            if ($sessionData !== null) {
                $sessionData = json_decode($sessionData, true);
            }
            if (!is_array($sessionData)) {
                return new DataResponse(['files' => []]);
            }

            $statusMap = [
                'pending' => 'PENDING',
                'processing' => 'STARTED',
                'completed' => 'SUCCESS',
                'failed' => 'FAILURE'
            ];

            $files = [];
            foreach ($sessionData as $item) {
                $taskId = $item['taskId'] ?? '';
                if ($taskId === '') {
                    continue;
                }

                try {
                    $task = $this->conversionService->getTask($taskId);
                    $status = $statusMap[$task->getStatus()] ?? 'PENDING';
                    
                    $fileItem = [
                        'taskId' => $taskId,
                        'name' => $item['name'] ?? $task->getOriginalFilename(),
                        'size' => $item['size'] ?? 0,
                        'status' => $status
                    ];

                    if ($task->getStatus() === 'completed') {
                        $fileItem['result'] = [
                            'success' => true,
                            'filename' => $task->getOriginalFilename()
                        ];
                    } elseif ($task->getStatus() === 'failed') {
                        $fileItem['error'] = $task->getErrorMessage();
                    }
                    
                    $files[] = $fileItem;
                } catch (DoesNotExistException $e) {
                    // Task no longer in database, skip it
                    continue;
                }
            }

            return new DataResponse(['files' => $files]);

        } catch (DoesNotExistException $e) {
            return new DataResponse(['error' => 'Folder not found'], Http::STATUS_NOT_FOUND);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Get conversion task status
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @PublicPage
     * @Guest
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    #[PublicPage]
    public function taskStatus(string $taskId): DataResponse {
        try {
            $task = $this->conversionService->getTask($taskId);

            // Map task status to frontend interface expectations
            $statusMap = [
                'pending' => 'PENDING',
                'processing' => 'STARTED',
                'completed' => 'SUCCESS',
                'failed' => 'FAILURE'
            ];

            $response = [
                'task_id' => $task->getId(),
                'status' => $statusMap[$task->getStatus()] ?? 'PENDING'
            ];

            if ($task->getStatus() === 'completed') {
                $response['result'] = [
                    'success' => true,
                    'filename' => $task->getOriginalFilename() // return name
                ];
            } elseif ($task->getStatus() === 'failed') {
                $response['error'] = $task->getErrorMessage();
            }

            return new DataResponse($response);
        } catch (DoesNotExistException $e) {
            return new DataResponse(['error' => 'Task not found'], Http::STATUS_NOT_FOUND);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }
}
