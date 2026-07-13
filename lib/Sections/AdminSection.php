<?php
namespace OCA\GroupPhotoSorter\Sections;

use OCP\Settings\IIconSection;

class AdminSection implements IIconSection {
    public function getID(): string {
        return 'group_photo_sorter';
    }

    public function getName(): string {
        return 'Group Photo Sorter';
    }

    public function getPriority(): int {
        return 80;
    }

    public function getIcon(): string {
        return 'group_photo_sorter-app'; 
    }
}
