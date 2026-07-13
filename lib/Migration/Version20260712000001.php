<?php

namespace OCA\GroupPhotoSorter\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

class Version20260712000001 extends SimpleMigrationStep {

    public function preSchema(IOutput $output, Closure $schemaClosure, array $options) {
        // No pre-schema actions needed
    }

    public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper {
        /** @var ISchemaWrapper $schema */
        $schema = $schemaClosure();

        if ($schema->hasTable('gps_folders')) {
            $table = $schema->getTable('gps_folders');
            if (!$table->hasColumn('is_active')) {
                $table->addColumn('is_active', 'boolean', [
                    'notnull' => false,
                    'default' => true,
                ]);
            }
        }

        return $schema;
    }

    public function postSchema(IOutput $output, Closure $schemaClosure, array $options) {
        // No post-schema actions needed
    }
}
