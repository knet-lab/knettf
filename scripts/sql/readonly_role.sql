-- 线上只读角色：供 scripts/ 的同步、快照、导出使用。
--
-- 执行方式（由线上管理员手动执行，脚本不会运行这个文件）：
--   1. 生成强密码，替换下面的 CHANGE_ME，密码不要提交到 Git。
--   2. 用超级用户连接线上库（容器 pg，库 vigil）：
--        docker exec -i pg psql -U <超级用户> -d vigil -v ON_ERROR_STOP=1 < scripts/sql/readonly_role.sql
--   3. 执行末尾的验证语句，确认 knettf_reader 没有写权限。
--
-- 之后在开发机设置（不要写进仓库，建议放在 ~/.config/knettf/reader.env，权限 600）：
--   KNETTF_SRC_USER=knettf_reader
--   KNETTF_SRC_PASSWORD=<上面的密码>

CREATE ROLE knettf_reader LOGIN PASSWORD 'CHANGE_ME';

GRANT CONNECT ON DATABASE vigil TO knettf_reader;
GRANT USAGE ON SCHEMA public TO knettf_reader;
GRANT SELECT ON TABLE vigil_collectrecord TO knettf_reader;
-- 不授予 INSERT / UPDATE / DELETE / TRUNCATE，不授予任何其他表的权限。

-- 验证：以下结果应全部为 f（false），rolsuper 为 f
SELECT has_table_privilege('knettf_reader', 'vigil_collectrecord', 'INSERT')   AS can_insert,
       has_table_privilege('knettf_reader', 'vigil_collectrecord', 'UPDATE')   AS can_update,
       has_table_privilege('knettf_reader', 'vigil_collectrecord', 'DELETE')   AS can_delete,
       has_table_privilege('knettf_reader', 'vigil_collectrecord', 'TRUNCATE') AS can_truncate,
       (SELECT rolsuper FROM pg_roles WHERE rolname = 'knettf_reader')         AS is_superuser;
