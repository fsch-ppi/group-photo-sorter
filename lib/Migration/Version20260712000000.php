<?php

namespace OCA\GroupPhotoSorter\Migration;

use OCP\Migration\SimpleMigrationStep;
use OCP\Migration\IOutput;
use OCP\DB\ISchemaWrapper;

class Version20260712000000 extends SimpleMigrationStep {

    public function preSchema(IOutput $output, \Closure $schemaClosure, array $options) {
        // No pre-schema actions needed
    }

    public function changeSchema(IOutput $output, \Closure $schemaClosure, array $options) {
        /** @var ISchemaWrapper $schema */
        $schema = $schemaClosure();

        // 1. Folders table
        if (!$schema->hasTable('gps_folders')) {
            $table = $schema->createTable('gps_folders');
            $table->addColumn('id', 'integer', [
                'autoincrement' => true,
                'notnull' => true,
                'length' => 11,
            ]);
            $table->addColumn('owner_id', 'string', [
                'notnull' => true,
                'length' => 64,
            ]);
            $table->addColumn('display_name', 'string', [
                'notnull' => true,
                'length' => 255,
            ]);
            $table->addColumn('event_name', 'string', [
                'notnull' => true,
                'length' => 255,
            ]);
            $table->addColumn('nextcloud_folder_path', 'string', [
                'notnull' => true,
                'length' => 512,
            ]);
            $table->addColumn('naming_format', 'string', [
                'notnull' => true,
                'length' => 64,
            ]);
            $table->addColumn('jpeg_quality', 'integer', [
                'notnull' => true,
                'default' => 90,
                'length' => 4,
            ]);
            $table->addColumn('video_crf', 'integer', [
                'notnull' => true,
                'default' => 23,
                'length' => 4,
            ]);
            $table->addColumn('token', 'string', [
                'notnull' => true,
                'length' => 32,
            ]);
            $table->addColumn('nc_share_token', 'string', [
                'notnull' => false,
                'length' => 32,
            ]);
            $table->addColumn('readme_message', 'text', [
                'notnull' => false,
            ]);
            $table->addColumn('created_at', 'datetime', [
                'notnull' => true,
            ]);

            $table->setPrimaryKey(['id']);
            $table->addUniqueIndex(['token'], 'gps_folders_tok_idx');
        }

        // 2. Statistics table
        if (!$schema->hasTable('gps_stats')) {
            $table = $schema->createTable('gps_stats');
            $table->addColumn('id', 'integer', [
                'autoincrement' => true,
                'notnull' => true,
                'length' => 11,
            ]);
            $table->addColumn('folder_id', 'integer', [
                'notnull' => true,
                'length' => 11,
            ]);
            $table->addColumn('uploader_ip', 'string', [
                'notnull' => true,
                'length' => 45,
            ]);
            $table->addColumn('filename_original', 'string', [
                'notnull' => true,
                'length' => 255,
            ]);
            $table->addColumn('filename_converted', 'string', [
                'notnull' => true,
                'length' => 255,
            ]);
            $table->addColumn('file_size_original', 'bigint', [
                'notnull' => true,
            ]);
            $table->addColumn('file_size_converted', 'bigint', [
                'notnull' => true,
            ]);
            $table->addColumn('file_type', 'string', [
                'notnull' => true,
                'length' => 16,
            ]);
            $table->addColumn('conversion_time_seconds', 'decimal', [
                'notnull' => true,
                'precision' => 8,
                'scale' => 2,
            ]);
            $table->addColumn('uploaded_at', 'datetime', [
                'notnull' => true,
            ]);

            $table->setPrimaryKey(['id']);
            $table->addIndex(['folder_id'], 'gps_stats_fld_idx');
        }

        // 3. Tasks table
        if (!$schema->hasTable('gps_tasks')) {
            $table = $schema->createTable('gps_tasks');
            $table->addColumn('id', 'string', [
                'notnull' => true,
                'length' => 64,
            ]);
            $table->addColumn('folder_id', 'integer', [
                'notnull' => true,
                'length' => 11,
            ]);
            $table->addColumn('status', 'string', [
                'notnull' => true,
                'length' => 32,
            ]);
            $table->addColumn('pid', 'integer', [
                'notnull' => false,
                'length' => 11,
            ]);
            $table->addColumn('original_filename', 'string', [
                'notnull' => true,
                'length' => 255,
            ]);
            $table->addColumn('temp_path', 'string', [
                'notnull' => true,
                'length' => 512,
            ]);
            $table->addColumn('output_path', 'string', [
                'notnull' => true,
                'length' => 512,
            ]);
            $table->addColumn('error_message', 'text', [
                'notnull' => false,
            ]);
            $table->addColumn('created_at', 'datetime', [
                'notnull' => true,
            ]);
            $table->addColumn('updated_at', 'datetime', [
                'notnull' => true,
            ]);

            $table->setPrimaryKey(['id']);
            $table->addIndex(['folder_id'], 'gps_tasks_fld_idx');
        }
        return $schema;
    }

    public function postSchema(IOutput $output, \Closure $schemaClosure, array $options) {
        // No post-schema actions needed
    }
}
