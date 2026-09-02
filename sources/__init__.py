from . import simplify, speedyapply_backup

BACKUP_SOURCES = {
    "simplify": simplify.fetch,
    "speedyapply_new_grad": speedyapply_backup.fetch,
}
