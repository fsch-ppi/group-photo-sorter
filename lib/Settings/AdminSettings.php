<?php
namespace OCA\GroupPhotoSorter\Settings;

use OCP\Settings\ISettings;
use OCP\AppFramework\Http\TemplateResponse;

class AdminSettings implements ISettings {
    
    public function getForm(): TemplateResponse {
        $hasPython = $this->checkCommand('python3');
        $hasFfmpeg = $this->checkCommand('ffmpeg');
        $hasFfprobe = $this->checkCommand('ffprobe');
        $execEnabled = function_exists('exec') && !in_array('exec', explode(',', ini_get('disable_functions')));

        $pythonLibs = ['pillow' => false, 'pillow_heif' => false, 'rawpy' => false];
        if ($hasPython && $execEnabled) {
            // Check if virtual env Python exists, check its packages too
            $pythonBin = __DIR__ . '/../../venv/bin/python3';
            if (!file_exists($pythonBin)) {
                $pythonBin = __DIR__ . '/../../.venv/bin/python3';
                if (!file_exists($pythonBin)) {
                    $pythonBin = 'python3';
                }
            }

            foreach (array_keys($pythonLibs) as $lib) {
                $output = [];
                $returnVal = -1;
                // Map the library key to its python import name
                $importName = $lib === 'pillow' ? 'PIL' : str_replace('-', '_', $lib);
                @exec(escapeshellarg($pythonBin) . " -c \"import $importName\" 2>&1", $output, $returnVal);
                if ($returnVal === 0) {
                    $pythonLibs[$lib] = true;
                }
            }
        }

        return new TemplateResponse('group_photo_sorter', 'admin_settings', [
            'hasPython' => $hasPython,
            'hasFfmpeg' => $hasFfmpeg,
            'hasFfprobe' => $hasFfprobe,
            'execEnabled' => $execEnabled,
            'pythonLibs' => $pythonLibs
        ]);
    }

    public function getSection(): string {
        return 'group_photo_sorter';
    }

    public function getPriority(): int {
        return 10;
    }

    private function checkCommand(string $cmd): bool {
        if (!function_exists('exec') || in_array('exec', explode(',', ini_get('disable_functions')))) {
            return false;
        }
        $output = [];
        $returnVal = -1;
        @exec("which " . escapeshellarg($cmd) . " 2>&1", $output, $returnVal);
        return $returnVal === 0;
    }
}
