<?php

namespace OCA\GroupPhotoSorter\Db;

use OCP\AppFramework\Db\QBMapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

class UploadStatsMapper extends QBMapper {

    public function __construct(IDBConnection $db) {
        parent::__construct($db, 'gps_stats', UploadStats::class);
    }

    /**
     * Get statistics for a folder
     */
    public function getFolderStats(int $folderId): array {
        // 1. Totals
        $qb = $this->db->getQueryBuilder();
        $qb->select()
           ->selectAlias($qb->func()->count('id'), 'total_uploads')
           ->selectAlias($qb->func()->sum('file_size_original'), 'total_original')
           ->selectAlias($qb->func()->sum('file_size_converted'), 'total_converted')
           ->from($this->tableName)
           ->where($qb->expr()->eq('folder_id', $qb->createNamedParameter($folderId, IQueryBuilder::PARAM_INT)));

        $row = $qb->executeQuery()->fetch(\PDO::FETCH_ASSOC);
        $totalUploads = (int)($row['total_uploads'] ?? 0);
        $totalOriginal = (int)($row['total_original'] ?? 0);
        $totalConverted = (int)($row['total_converted'] ?? 0);

        // 2. Uploads by IP
        $qb = $this->db->getQueryBuilder();
        $qb->select('uploader_ip', $qb->func()->count('id', 'count'))
           ->from($this->tableName)
           ->where($qb->expr()->eq('folder_id', $qb->createNamedParameter($folderId, IQueryBuilder::PARAM_INT)))
           ->groupBy('uploader_ip');

        $ipRows = $qb->executeQuery()->fetchAll(\PDO::FETCH_ASSOC);
        $uploadsByIp = [];
        foreach ($ipRows as $ipRow) {
            $uploadsByIp[$ipRow['uploader_ip']] = (int)$ipRow['count'];
        }

        // 3. Recent uploads
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
           ->from($this->tableName)
           ->where($qb->expr()->eq('folder_id', $qb->createNamedParameter($folderId, IQueryBuilder::PARAM_INT)))
           ->orderBy('uploaded_at', 'DESC')
           ->setMaxResults(20);

        $recentUploads = $this->findEntities($qb);

        return [
            'total_uploads' => $totalUploads,
            'total_size_original_bytes' => $totalOriginal,
            'total_size_converted_bytes' => $totalConverted,
            'uploads_by_ip' => $uploadsByIp,
            'recent_uploads' => $recentUploads,
        ];
    }

    /**
     * Get count of uploads for a folder
     */
    public function getUploadCount(int $folderId): int {
        $qb = $this->db->getQueryBuilder();
        $qb->select($qb->func()->count('id', 'count'))
           ->from($this->tableName)
           ->where($qb->expr()->eq('folder_id', $qb->createNamedParameter($folderId, IQueryBuilder::PARAM_INT)));
        $row = $qb->executeQuery()->fetch(\PDO::FETCH_ASSOC);
        return (int)($row['count'] ?? 0);
    }

    /**
     * Anonymize IPs older than a cutoff date (GDPR)
     */
    public function anonymizeOldIps(\DateTime $cutoffDate): int {
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->tableName)
           ->set('uploader_ip', $qb->createNamedParameter('xxx.xxx.xxx.xxx'))
           ->where($qb->expr()->lt('uploaded_at', $qb->createNamedParameter($cutoffDate, IQueryBuilder::PARAM_DATE)))
           ->andWhere($qb->expr()->neq('uploader_ip', $qb->createNamedParameter('xxx.xxx.xxx.xxx')));
        return $qb->executeStatement();
    }

    /**
     * Delete all statistics for a folder
     */
    public function deleteForFolder(int $folderId): void {
        $qb = $this->db->getQueryBuilder();
        $qb->delete($this->tableName)
           ->where($qb->expr()->eq('folder_id', $qb->createNamedParameter($folderId, IQueryBuilder::PARAM_INT)));
        $qb->executeStatement();
    }
}

