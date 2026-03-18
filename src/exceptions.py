"""
自定义异常类

@input 无外部依赖
@output AutoTestError基类及所有子异常类 (1xxx-9xxx错误码)
@pos 核心基础模块，提供详细的错误信息和错误码分类

错误码规则：
  1xxx - 配置相关错误
  2xxx - 工程生成相关错误
  3xxx - 工程构建相关错误
  4xxx - 测试执行相关错误
  5xxx - 日志相关错误
  9xxx - 其他错误

一旦我被更新务必更新我的开头注释以及所属文件夹的 README.md
"""

class AutoTestError(Exception):
    """基础异常类"""
    
    def __init__(self, message: str, error_code: int = 9000, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        base = f"[E{self.error_code:04d}] {self.message}"
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{base} ({details_str})"
        return base
    
    def __str__(self) -> str:
        return self._format_message()


class ConfigError(AutoTestError):
    """配置相关错误 (1xxx)"""
    
    def __init__(self, message: str, error_code: int = 1000, details: dict = None):
        super().__init__(message, error_code, details)


class ConfigFileNotFoundError(ConfigError):
    """配置文件不存在"""
    
    def __init__(self, path: str):
        super().__init__(
            f"配置文件不存在: {path}",
            error_code=1001,
            details={"path": path}
        )


class ConfigValidationError(ConfigError):
    """配置验证失败"""
    
    def __init__(self, field: str, reason: str, value=None):
        details = {"field": field, "reason": reason}
        if value is not None:
            details["value"] = str(value)
        super().__init__(
            f"配置验证失败: 字段 '{field}' {reason}",
            error_code=1002,
            details=details
        )


class ConfigPathError(ConfigError):
    """路径配置错误"""
    
    def __init__(self, path_type: str, path: str, reason: str):
        super().__init__(
            f"路径配置错误: {path_type} - {reason}",
            error_code=1003,
            details={"path_type": path_type, "path": path, "reason": reason}
        )


class GeneratorError(AutoTestError):
    """工程生成相关错误 (2xxx)"""
    
    def __init__(self, message: str, error_code: int = 2000, details: dict = None):
        super().__init__(message, error_code, details)


class TemplateNotFoundError(GeneratorError):
    """模板工程不存在"""
    
    def __init__(self, path: str):
        super().__init__(
            f"模板工程目录不存在: {path}",
            error_code=2001,
            details={"path": path}
        )


class SourceFileError(GeneratorError):
    """源文件错误"""
    
    def __init__(self, path: str, reason: str):
        super().__init__(
            f"源文件错误: {reason}",
            error_code=2002,
            details={"path": path, "reason": reason}
        )


class ProjectGenerationError(GeneratorError):
    """工程生成失败"""
    
    def __init__(self, project_name: str, reason: str):
        super().__init__(
            f"工程生成失败: {project_name} - {reason}",
            error_code=2003,
            details={"project_name": project_name, "reason": reason}
        )


class BuildError(AutoTestError):
    """工程构建相关错误 (3xxx)"""
    
    def __init__(self, message: str, error_code: int = 3000, details: dict = None):
        super().__init__(message, error_code, details)


class CCSNotFoundError(BuildError):
    """CCS 未找到"""
    
    def __init__(self, path: str):
        super().__init__(
            f"CCS 可执行文件不存在: {path}",
            error_code=3001,
            details={"path": path}
        )


class ProjectImportError(BuildError):
    """工程导入失败"""
    
    def __init__(self, project_name: str, reason: str, stdout: str = None):
        details = {"project_name": project_name, "reason": reason}
        if stdout:
            details["stdout"] = stdout[:500]
        super().__init__(
            f"工程导入失败: {project_name} - {reason}",
            error_code=3002,
            details=details
        )


class ProjectBuildError(BuildError):
    """工程构建失败"""
    
    def __init__(self, project_name: str, reason: str, stdout: str = None):
        details = {"project_name": project_name, "reason": reason}
        if stdout:
            details["stdout"] = stdout[:500]
        super().__init__(
            f"工程构建失败: {project_name} - {reason}",
            error_code=3003,
            details=details
        )


class BuildTimeoutError(BuildError):
    """构建超时"""
    
    def __init__(self, project_name: str, timeout: int):
        super().__init__(
            f"工程构建超时: {project_name} (超时 {timeout} 秒)",
            error_code=3004,
            details={"project_name": project_name, "timeout": timeout}
        )


class TestError(AutoTestError):
    """测试执行相关错误 (4xxx)"""
    
    def __init__(self, message: str, error_code: int = 4000, details: dict = None):
        super().__init__(message, error_code, details)


class DSSNotFoundError(TestError):
    """DSS 脚本执行器未找到"""
    
    def __init__(self, path: str):
        super().__init__(
            f"DSS 执行器不存在: {path}",
            error_code=4001,
            details={"path": path}
        )


class TargetConnectionError(TestError):
    """目标板连接失败"""
    
    def __init__(self, device: str, cpu: str, reason: str):
        super().__init__(
            f"目标板连接失败: {device}/{cpu} - {reason}",
            error_code=4002,
            details={"device": device, "cpu": cpu, "reason": reason}
        )


class ProgramLoadError(TestError):
    """程序加载失败"""
    
    def __init__(self, out_file: str, reason: str):
        super().__init__(
            f"程序加载失败: {out_file} - {reason}",
            error_code=4003,
            details={"out_file": out_file, "reason": reason}
        )


class TestExecutionError(TestError):
    """测试执行失败"""
    
    def __init__(self, case_name: str, reason: str):
        super().__init__(
            f"测试执行失败: {case_name} - {reason}",
            error_code=4004,
            details={"case_name": case_name, "reason": reason}
        )


class TestTimeoutError(TestError):
    """测试超时"""
    
    def __init__(self, case_name: str, timeout: int):
        super().__init__(
            f"测试执行超时: {case_name} (超时 {timeout} 毫秒)",
            error_code=4005,
            details={"case_name": case_name, "timeout": timeout}
        )


class MemoryExportError(TestError):
    """内存导出失败"""
    
    def __init__(self, segment: str, reason: str):
        super().__init__(
            f"内存导出失败: {segment} - {reason}",
            error_code=4006,
            details={"segment": segment, "reason": reason}
        )


class LoggerError(AutoTestError):
    """日志相关错误 (5xxx)"""
    
    def __init__(self, message: str, error_code: int = 5000, details: dict = None):
        super().__init__(message, error_code, details)


class LogDirectoryError(LoggerError):
    """日志目录错误"""
    
    def __init__(self, path: str, reason: str):
        super().__init__(
            f"日志目录错误: {reason}",
            error_code=5001,
            details={"path": path, "reason": reason}
        )
