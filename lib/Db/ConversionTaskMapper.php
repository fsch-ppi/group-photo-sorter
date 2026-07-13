<?php

namespace OCA\GroupPhotoSorter\Db;

use OCP\AppFramework\Db\QBMapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

class ConversionTaskMapper extends QBMapper {

    public function __construct(IDBConnection $db) {
        parent::__construct($db, 'gps_tasks', ConversionTask::class);
    }

    /**
     * Find task by its UUID string ID
     */
    public function find(string $id): ConversionTask {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
           ->from($this->tableName)
           ->where($qb->expr()->eq('id', $qb->createNamedParameter($id)));
        return $this->findEntity($qb);
    }

    /**
     * Find all pending tasks
     * @return ConversionTask[]
     */
    public function findPending(): array {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
           ->from($this->tableName)
           ->where($qb->expr()->eq('status', $qb->createNamedParameter('pending')))
           ->orderBy('created_at', 'ASC');
        return $this->findEntities($qb);
    }

    /**
     * Find all processing tasks
     * @return ConversionTask[]
     */
    public function findProcessing(): array {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
           ->from($this->tableName)
           ->where($qb->expr()->eq('status', $qb->createNamedParameter('processing')));
        return $this->findEntities($qb);
    }

    /**
     * Insert a task with a string ID
     */
    public function insertTask(ConversionTask $task): void {
        $qb = $this->db->getQueryBuilder();
        $qb->insert($this->tableName)
           ->values([
               'id' => $qb->createNamedParameter($task->getId()),
               'folder_id' => $qb->createNamedParameter($task->getFolderId(), IQueryBuilder::PARAM_INT),
               'status' => $qb->createNamedParameter($task->getStatus()),
               'pid' => $qb->createNamedParameter($task->getPid(), IQueryBuilder::PARAM_INT),
               'original_filename' => $qb->createNamedParameter($task->getOriginalFilename()),
               'temp_path' => $qb->createNamedParameter($task->getTempPath()),
               'output_path' => $qb->createNamedParameter($task->getOutputPath()),
               'error_message' => $qb->createNamedParameter($task->getErrorMessage()),
               'created_at' => $qb->createNamedParameter($task->getCreatedAt(), IQueryBuilder::PARAM_DATE),
               'updated_at' => $qb->createNamedParameter($task->getUpdatedAt(), IQueryBuilder::PARAM_DATE),
           ]);
        $qb->executeStatement();
    }

    /**
     * Update a task
     */
    public function updateTask(ConversionTask $task): void {
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->tableName)
           ->set('status', $qb->createNamedParameter($task->getStatus()))
           ->set('pid', $qb->createNamedParameter($task->getPid(), IQueryBuilder::PARAM_INT))
           ->set('error_message', $qb->createNamedParameter($task->getErrorMessage()))
           ->set('updated_at', $qb->createNamedParameter($task->getUpdatedAt(), IQueryBuilder::PARAM_DATE))
           ->where($qb->expr()->eq('id', $qb->createNamedParameter($task->getId())));
        $qb->executeStatement();
    }

    /**
     * Try to atomically claim a task for processing.
     * Returns true if successfully claimed, false otherwise.
     */
    public function claimTask(string $id, int $pid): bool {
        $qb = $this->db->getQueryBuilder();
        $qb->update($this->tableName)
           ->set('status', $qb->createNamedParameter('processing'))
           ->set('pid', $qb->createNamedParameter($pid, IQueryBuilder::PARAM_INT))
           ->set('updated_at', $qb->createNamedParameter(new \DateTime(), IQueryBuilder::PARAM_DATE))
           ->where($qb->expr()->eq('id', $qb->createNamedParameter($id)))
           ->andWhere($qb->expr()->eq('status', $qb->createNamedParameter('pending')));
        
        $affectedRows = $qb->executeStatement();
        return $affectedRows > 0;
    }

    /**
     * Delete a task
     */
    public function deleteTask(ConversionTask $task): void {
        $qb = $this->db->getQueryBuilder();
        $qb->delete($this->tableName)
           ->where($qb->expr()->eq('id', $qb->createNamedParameter($task->getId())));
        $qb->executeStatement();
    }

    /**
     * Delete tasks older than a specific date
     */
    public function deleteTasksOlderThan(\DateTime $cutoffDate, ?array $statuses = null): void {
        $qb = $this->db->getQueryBuilder();
        $qb->delete($this->tableName)
           ->where($qb->expr()->lt('updated_at', $qb->createNamedParameter($cutoffDate, IQueryBuilder::PARAM_DATE)));
        
        if ($statuses !== null) {
            $qb->andWhere($qb->expr()->in('status', $qb->createNamedParameter($statuses, IQueryBuilder::PARAM_STR_ARRAY)));
        }
        
        $qb->executeStatement();
     }

    /**
     * Delete all tasks for a folder
     */
    public function deleteForFolder(int $folderId): void {
        $qb = $this->db->getQueryBuilder();
        $qb->delete($this->tableName)
           ->where($qb->expr()->eq('folder_id', $qb->createNamedParameter($folderId, IQueryBuilder::PARAM_INT)));
        $qb->executeStatement();
    }
}

