<?php

namespace OCA\GroupPhotoSorter\Db;

use OCP\AppFramework\Db\QBMapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

class FolderMapper extends QBMapper {

    public function __construct(IDBConnection $db) {
        parent::__construct($db, 'gps_folders', Folder::class);
    }

    /**
     * Find a folder by its database ID
     */
    public function find(int $id): Folder {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
           ->from($this->tableName)
           ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)));
        return $this->findEntity($qb);
    }

    /**
     * Find all folders owned by a specific Nextcloud user
     * @return Folder[]
     */
    public function findByOwner(string $ownerId): array {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
           ->from($this->tableName)
           ->where($qb->expr()->eq('owner_id', $qb->createNamedParameter($ownerId)))
           ->orderBy('created_at', 'DESC');
        return $this->findEntities($qb);
    }

    /**
     * Find a folder by its share token
     */
    public function findByToken(string $token): Folder {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
           ->from($this->tableName)
           ->where($qb->expr()->eq('token', $qb->createNamedParameter($token)));
        return $this->findEntity($qb);
    }
}
