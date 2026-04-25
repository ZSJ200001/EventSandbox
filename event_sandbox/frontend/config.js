// EventSandbox 前端配置文件
// 修改这里的配置来连接不同的后端服务

const CONFIG = {
    API_HOST: 'localhost',      // 后端服务器地址
    API_PORT: '8010',          // 后端服务端口
    API_BASE_PATH: '/api'      // API路径前缀
};

// 导出配置供其他模块使用
window.EVENT_SANDBOX_CONFIG = CONFIG;
