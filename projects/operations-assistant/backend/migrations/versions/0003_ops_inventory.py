"""Create the three-table synthetic inventory exercise."""
from alembic import op
import sqlalchemy as sa

revision = "0003_ops_inventory"
down_revision = "0002_demo_inventory"
branch_labels = None
depends_on = None


def upgrade():
    # 兼容学生已手动创建部分练习表的情况，保留已有数据。
    op.execute("""CREATE TABLE IF NOT EXISTS ops_products (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        sku VARCHAR(64) NOT NULL,
        name VARCHAR(128) NOT NULL,
        UNIQUE KEY uq_ops_product_sku (sku)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    op.execute("""CREATE TABLE IF NOT EXISTS ops_stores (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        code VARCHAR(64) NOT NULL,
        name VARCHAR(128) NOT NULL,
        UNIQUE KEY uq_ops_store_code (code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    op.execute("""CREATE TABLE IF NOT EXISTS ops_inventory (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        store_id BIGINT NOT NULL,
        product_id BIGINT NOT NULL,
        available INT UNSIGNED NOT NULL DEFAULT 0,
        reserved INT UNSIGNED NOT NULL DEFAULT 0,
        inbound INT UNSIGNED NOT NULL DEFAULT 0,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_ops_inventory_store_product (store_id, product_id),
        CONSTRAINT fk_ops_inventory_store FOREIGN KEY (store_id) REFERENCES ops_stores(id),
        CONSTRAINT fk_ops_inventory_product FOREIGN KEY (product_id) REFERENCES ops_products(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    connection = op.get_bind()
    for sku, name in [("OPS-EARBUDS-001", "无线耳机"), ("OPS-LAMP-002", "阅读台灯")]:
        connection.execute(sa.text("""INSERT INTO ops_products (sku, name)
            SELECT :sku, :name WHERE NOT EXISTS
            (SELECT 1 FROM ops_products WHERE sku = :sku)"""), {"sku": sku, "name": name})
    for code, name in [("OPS-GZ", "广州演示店"), ("OPS-SZ", "深圳演示店")]:
        connection.execute(sa.text("""INSERT INTO ops_stores (code, name)
            SELECT :code, :name WHERE NOT EXISTS
            (SELECT 1 FROM ops_stores WHERE code = :code)"""), {"code": code, "name": name})
    for code, sku, available, reserved, inbound in [
        ("OPS-GZ", "OPS-EARBUDS-001", 28, 8, 120),
        ("OPS-SZ", "OPS-EARBUDS-001", 6, 2, 40),
    ]:
        # 仅补齐缺失的模拟库存；已存在的学生练习结果保持原值。
        connection.execute(sa.text("""INSERT INTO ops_inventory
            (store_id, product_id, available, reserved, inbound)
            SELECT s.id, p.id, :available, :reserved, :inbound
            FROM ops_stores s CROSS JOIN ops_products p
            WHERE s.code = :code AND p.sku = :sku AND NOT EXISTS
            (SELECT 1 FROM ops_inventory i WHERE i.store_id = s.id AND i.product_id = p.id)
        """), dict(code=code, sku=sku, available=available, reserved=reserved, inbound=inbound))


def downgrade():
    # 练习表可能包含学生手动创建的数据，回退时显式保护。
    raise RuntimeError("This lesson migration retains learner data; archive the tables before manual rollback.")
