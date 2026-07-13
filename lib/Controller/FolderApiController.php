<?php

namespace OCA\GroupPhotoSorter\Controller;

use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\DataResponse;
use OCP\IRequest;
use OCP\IUserSession;
use OCP\AppFramework\Http;
use OCP\AppFramework\Db\DoesNotExistException;
use OCA\GroupPhotoSorter\Service\FolderService;
use OCA\GroupPhotoSorter\Db\UploadStatsMapper;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;

class FolderApiController extends Controller {

    private FolderService $folderService;
    private UploadStatsMapper $statsMapper;
    private IUserSession $userSession;

    public function __construct(
        string $appName,
        IRequest $request,
        FolderService $folderService,
        UploadStatsMapper $statsMapper,
        IUserSession $userSession
    ) {
        parent::__construct($appName, $request);
        $this->folderService = $folderService;
        $this->statsMapper = $statsMapper;
        $this->userSession = $userSession;
    }

    private function getUserId(): string {
        $user = $this->userSession->getUser();
        if ($user === null) {
            throw new \UnauthorizedException("User not logged in");
        }
        return $user->getUID();
    }

    /**
     * List all folders owned by the logged-in user
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function index(): DataResponse {
        try {
            $userId = $this->getUserId();
            $folders = $this->folderService->list($userId);
            return new DataResponse(['results' => $folders]);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_UNAUTHORIZED);
        }
    }

    /**
     * Get details of a single folder
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function show(int $id): DataResponse {
        try {
            $userId = $this->getUserId();
            $folder = $this->folderService->get($id, $userId);
            return new DataResponse($folder);
        } catch (DoesNotExistException $e) {
            return new DataResponse(['error' => 'Folder not found'], Http::STATUS_NOT_FOUND);
        } catch (\UnauthorizedException $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_FORBIDDEN);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Create a new folder
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function create(): DataResponse {
        try {
            $userId = $this->getUserId();
            $params = $this->request->getParams();
            $folder = $this->folderService->create($userId, $params);
            return new DataResponse($folder, Http::STATUS_CREATED);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Update an existing folder
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function update(int $id): DataResponse {
        try {
            $userId = $this->getUserId();
            $params = $this->request->getParams();
            $folder = $this->folderService->update($id, $userId, $params);
            return new DataResponse($folder);
        } catch (DoesNotExistException $e) {
            return new DataResponse(['error' => 'Folder not found'], Http::STATUS_NOT_FOUND);
        } catch (\UnauthorizedException $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_FORBIDDEN);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Delete folder configuration
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function destroy(int $id): DataResponse {
        try {
            $userId = $this->getUserId();
            $this->folderService->delete($id, $userId);
            return new DataResponse(null, Http::STATUS_NO_CONTENT);
        } catch (DoesNotExistException $e) {
            return new DataResponse(['error' => 'Folder not found'], Http::STATUS_NOT_FOUND);
        } catch (\UnauthorizedException $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_FORBIDDEN);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Regenerate share token
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function regenerateToken(int $id): DataResponse {
        try {
            $userId = $this->getUserId();
            $folder = $this->folderService->regenerateToken($id, $userId);
            return new DataResponse([
                'share_token' => $folder->getToken(),
                'upload_url' => \OC::$server->getURLGenerator()->getAbsoluteURL(
                    \OC::$server->getURLGenerator()->linkToRoute('group_photo_sorter.page.uploadPage', ['token' => $folder->getToken()])
                )
            ]);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Regenerate Nextcloud share link
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function regenerateNextcloudShare(int $id): DataResponse {
        try {
            $userId = $this->getUserId();
            $folder = $this->folderService->regenerateNextcloudShare($id, $userId);
            $shareUrl = null;
            if ($folder->getNcShareToken()) {
                $shareUrl = \OC::$server->getURLGenerator()->getAbsoluteURL(
                    '/s/' . $folder->getNcShareToken()
                );
            }
            return new DataResponse([
                'nextcloud_share_token' => $folder->getNcShareToken(),
                'nextcloud_share_url' => $shareUrl
            ]);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Get statistics for a folder
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function statistics(int $id): DataResponse {
        try {
            $userId = $this->getUserId();
            // Verify ownership first
            $this->folderService->get($id, $userId);
            
            $stats = $this->statsMapper->getFolderStats($id);
            return new DataResponse($stats);
        } catch (\Exception $e) {
            return new DataResponse(['error' => $e->getMessage()], Http::STATUS_BAD_REQUEST);
        }
    }

    /**
     * Get naming format options
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function namingFormats(): DataResponse {
        $formats = [
            ['value' => 'DATE_EVENT', 'label' => 'Date & Event (YYYY-MM-DD_HHMMSS_event.ext)'],
            ['value' => 'EVENT_DATE', 'label' => 'Event & Date (event_YYYY-MM-DD_HHMMSS.ext)'],
            ['value' => 'DATE_ONLY', 'label' => 'Date & Time Only (YYYY-MM-DD_HHMMSS.ext)'],
            ['value' => 'DATE_DAY_ONLY', 'label' => 'Date Only (YYYY-MM-DD.ext)'],
            ['value' => 'DATE_DAY_EVENT', 'label' => 'Date & Event (YYYY-MM-DD_event.ext)'],
            ['value' => 'EVENT_DATE_DAY', 'label' => 'Event & Date (event_YYYY-MM-DD.ext)'],
            ['value' => 'DATE_HOUR_EVENT', 'label' => 'Date Hour & Event (YYYY-MM-DD_HH_event.ext)'],
            ['value' => 'EVENT_DATE_HOUR', 'label' => 'Event & Date Hour (event_YYYY-MM-DD_HH.ext)'],
            ['value' => 'ORIGINAL', 'label' => 'Keep Original Name'],
        ];
        return new DataResponse($formats);
    }
}
