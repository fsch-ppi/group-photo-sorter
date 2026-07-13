<?php

namespace OCA\GroupPhotoSorter\Controller;

use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\IRequest;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\PublicPage;

class PageController extends Controller {

    public function __construct(string $appName, IRequest $request) {
        parent::__construct($appName, $request);
    }

    /**
     * Admin Dashboard page (requires authentication)
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function index(): TemplateResponse {
        // Renders templates/index.php
        return new TemplateResponse($this->appName, 'index');
    }

    /**
     * Public Guest Upload page (no auth required)
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @PublicPage
     * @Guest
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    #[PublicPage]
    public function uploadPage(string $token): TemplateResponse {
        // Renders templates/upload.php
        return new TemplateResponse($this->appName, 'upload', ['token' => $token], 'guest');
    }
}
