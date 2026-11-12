-- ChatBI 数据库初始化（SDD §5.1 / §6.4）
-- 只建 schema、角色和授权，不建业务表。
-- data 业务表由 seed/schema.sql 建；app 表由 ORM create_all 建。

-- 1. 建 schema
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS data;

-- 2. 建只读角色（密码由环境变量覆盖）
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'chatbi_ro') THEN
    CREATE ROLE chatbi_ro LOGIN PASSWORD 'chatbi_ro';
  END IF;
END
$$;

-- 3. 授权：chatbi_ro 只读 data schema
GRANT USAGE ON SCHEMA data TO chatbi_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA data TO chatbi_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA data GRANT SELECT TO chatbi_ro;

-- 4. 确保 chatbi 读写角色有 app/data schema 权限
GRANT ALL ON SCHEMA app TO chatbi;
GRANT ALL ON SCHEMA data TO chatbi;
GRANT ALL ON ALL TABLES IN SCHEMA app TO chatbi;
GRANT ALL ON ALL TABLES IN SCHEMA data TO chatbi;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL TO chatbi;
ALTER DEFAULT PRIVILEGES IN SCHEMA data GRANT ALL TO chatbi;

-- 5. pgvector 扩展（可选，PGVECTOR_ENABLED=auto 时探测）
CREATE EXTENSION IF NOT EXISTS vector;

-- 6. 示例向量表（供 S3 检索使用；没有也不阻断）
--    维度 1024 与 EMBED_DIM 保持一致；pgvector 的 HNSW 索引要求列维度 ≤ 2000
CREATE TABLE IF NOT EXISTS app.exemplar_embeddings (
    exemplar_id TEXT NOT NULL,
    question TEXT NOT NULL,
    embedding vector(1024),
    model TEXT NOT NULL,
    dim INT NOT NULL,
    content_hash TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (exemplar_id, model)
);
CREATE INDEX IF NOT EXISTS idx_exemplar_embeddings_hnsw
    ON app.exemplar_embeddings USING hnsw (embedding vector_cosine_ops);
