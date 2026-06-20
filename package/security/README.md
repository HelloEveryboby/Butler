# 安全工具包 (Security Package)

本目录包含 Butler 系统中负责数据加密、身份验证和权限控制的核心模块。

## 模块说明

- **AccountPassword.py**: 账号密码管理器。支持 AES-256 加密存储、主密码验证、自动登录模拟和强密码生成。
- **encrypt.py**: 对称加密工具。提供 AES 和 DES 的字符串及文件加密功能，支持密钥派生。
- **asymmetric_tool.py**: 非对称加密工具。支持 RSA (加密/签名) 和 ECC (签名) 算法。
- **crypto_core.py**: 加解密核心库。底层调用 `pycryptodome` 实现，被上述所有安全工具调用。
- **Limits_of_authority.py**: 权限管理系统。基于角色和权限等级的操作过滤，支持文件完整性校验。
- **quarantine.py**: 文件隔离系统。用于将可疑文件移动到隔离区并进行管理。
- **authority_config.json**: 权限系统的配置文件，定义角色和权限级别。

## 使用方法

通常可以通过 Butler 的自然语言界面调用这些工具。例如：
- "打开密码管理器" -> `AccountPassword.py`
- "加密这个文件" -> `encrypt.py`
