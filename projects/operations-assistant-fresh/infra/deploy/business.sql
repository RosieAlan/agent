-- 教学合成业务数据；部署到独立数据库。

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `ops_stores` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `code` varchar(64) NOT NULL,
  `name` varchar(128) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ops_store_code` (`code`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT IGNORE INTO `ops_stores` (`id`,`code`,`name`) VALUES (1,'OPS-GZ','广州演示店');

INSERT IGNORE INTO `ops_stores` (`id`,`code`,`name`) VALUES (2,'OPS-SZ','深圳演示店');

CREATE TABLE IF NOT EXISTS `ops_products` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sku` varchar(64) NOT NULL,
  `name` varchar(128) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ops_product_sku` (`sku`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT IGNORE INTO `ops_products` (`id`,`sku`,`name`) VALUES (1,'OPS-EARBUDS-001','无线耳机');

INSERT IGNORE INTO `ops_products` (`id`,`sku`,`name`) VALUES (2,'OPS-LAMP-002','阅读台灯');

CREATE TABLE IF NOT EXISTS `ops_inventory` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `store_id` bigint NOT NULL,
  `product_id` bigint NOT NULL,
  `available` int unsigned NOT NULL DEFAULT '0',
  `reserved` int unsigned NOT NULL DEFAULT '0',
  `inbound` int unsigned NOT NULL DEFAULT '0',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ops_inventory_store_product` (`store_id`,`product_id`),
  KEY `fk_ops_inventory_product` (`product_id`),
  CONSTRAINT `fk_ops_inventory_product` FOREIGN KEY (`product_id`) REFERENCES `ops_products` (`id`),
  CONSTRAINT `fk_ops_inventory_store` FOREIGN KEY (`store_id`) REFERENCES `ops_stores` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT IGNORE INTO `ops_inventory` (`id`,`store_id`,`product_id`,`available`,`reserved`,`inbound`,`updated_at`) VALUES (1,1,1,28,8,120,'2026-11-05 10:29:07');

INSERT IGNORE INTO `ops_inventory` (`id`,`store_id`,`product_id`,`available`,`reserved`,`inbound`,`updated_at`) VALUES (2,2,1,6,2,40,'2026-11-05 10:29:07');
