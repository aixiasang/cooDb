document.addEventListener('DOMContentLoaded', function() {
  // 初始化配置
  const config = {
    baseUrl: window.location.origin
  };

  // 切换部分展开/折叠
  function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const content = section.querySelector('.section-content');
    const chevron = section.querySelector('.chevron-icon');
    
    content.classList.toggle('expanded');
    chevron.classList.toggle('expanded');
  }

  // 切换端点展开/折叠
  function toggleEndpoint(endpointId) {
    const content = document.getElementById(`${endpointId}-content`);
    const chevron = document.getElementById(`${endpointId}-chevron`);
    
    content.classList.toggle('expanded');
    chevron.classList.toggle('expanded');
  }

  // 复制到剪贴板
  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(
      function() {
        // 成功复制
        showMessage('已复制到剪贴板', 'success');
      }, 
      function() {
        // 复制失败
        showMessage('复制失败', 'error');
      }
    );
  }

  // 显示消息
  function showMessage(message, type = 'info') {
    const messageElement = document.createElement('div');
    messageElement.className = `message ${type}`;
    messageElement.textContent = message;
    
    document.body.appendChild(messageElement);
    
    setTimeout(() => {
      messageElement.classList.add('show');
      
      setTimeout(() => {
        messageElement.classList.remove('show');
        setTimeout(() => {
          document.body.removeChild(messageElement);
        }, 300);
      }, 2000);
    }, 10);
  }

  // 尝试调用API
  function tryItOut(endpointId) {
    const tryItBtn = document.getElementById(`${endpointId}-try-btn`);
    const tryItContainer = document.getElementById(`${endpointId}-try-container`);
    
    tryItBtn.disabled = true;
    tryItContainer.style.display = 'block';
  }

  // 取消尝试调用
  function cancelTryItOut(endpointId) {
    const tryItBtn = document.getElementById(`${endpointId}-try-btn`);
    const tryItContainer = document.getElementById(`${endpointId}-try-container`);
    
    tryItBtn.disabled = false;
    tryItContainer.style.display = 'none';
  }

  // 执行API调用
  async function executeRequest(endpointId) {
    const endpoint = document.getElementById(endpointId);
    const method = endpoint.dataset.method;
    const path = endpoint.dataset.path;
    const responseContainer = document.getElementById(`${endpointId}-response`);
    
    // 获取参数
    const paramInputs = document.querySelectorAll(`#${endpointId}-try-container .param-input`);
    const params = {};
    let url = path;
    
    paramInputs.forEach(input => {
      const name = input.dataset.name;
      const value = input.value;
      
      if (input.dataset.in === 'path') {
        url = url.replace(`{${name}}`, encodeURIComponent(value));
      } else if (input.dataset.in === 'query') {
        params[name] = value;
      }
    });
    
    // 构建查询字符串
    const queryParams = new URLSearchParams();
    for (const key in params) {
      if (params[key]) {
        queryParams.append(key, params[key]);
      }
    }
    
    const queryString = queryParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
    
    // 请求体
    let body = null;
    const requestBodyTextarea = document.getElementById(`${endpointId}-request-body`);
    if (requestBodyTextarea && ['POST', 'PUT', 'PATCH'].includes(method)) {
      try {
        body = JSON.parse(requestBodyTextarea.value);
      } catch (e) {
        showMessage('请求体格式错误: ' + e.message, 'error');
        return;
      }
    }
    
    // 显示加载状态
    responseContainer.innerHTML = '<div class="response-loading">Loading...</div>';
    responseContainer.style.display = 'block';
    
    try {
      // 发送请求
      const response = await fetch(`${config.baseUrl}${url}`, {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: body ? JSON.stringify(body) : undefined
      });
      
      const responseData = await response.json();
      
      // 显示响应
      responseContainer.innerHTML = `
        <div class="response-status ${response.ok ? 'success' : 'error'}">
          ${response.status} ${response.statusText}
        </div>
        <pre class="response-body">${JSON.stringify(responseData, null, 2)}</pre>
      `;
    } catch (error) {
      responseContainer.innerHTML = `
        <div class="response-status error">Error</div>
        <pre class="response-body">${error.message}</pre>
      `;
    }
  }

  // 初始化页面
  function init() {
    // 初始化折叠
    document.querySelectorAll('.section-header').forEach(header => {
      header.addEventListener('click', function() {
        const sectionId = this.parentElement.id;
        toggleSection(sectionId);
      });
    });
    
    // 初始化端点
    document.querySelectorAll('.endpoint-header').forEach(header => {
      header.addEventListener('click', function() {
        const endpointId = this.closest('.endpoint').id;
        toggleEndpoint(endpointId);
      });
    });
    
    // 初始化复制按钮
    document.querySelectorAll('.copy-icon').forEach(icon => {
      icon.addEventListener('click', function(e) {
        e.stopPropagation();
        const text = this.dataset.copy;
        copyToClipboard(text);
      });
    });
    
    // 初始化尝试按钮
    document.querySelectorAll('.try-it-out-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        const endpointId = this.dataset.endpoint;
        tryItOut(endpointId);
      });
    });
    
    // 初始化取消按钮
    document.querySelectorAll('.cancel-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        const endpointId = this.dataset.endpoint;
        cancelTryItOut(endpointId);
      });
    });
    
    // 初始化执行按钮
    document.querySelectorAll('.execute-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        const endpointId = this.dataset.endpoint;
        executeRequest(endpointId);
      });
    });
    
    // 默认展开第一个部分
    const firstSection = document.querySelector('.section');
    if (firstSection) {
      toggleSection(firstSection.id);
    }
  }

  // 初始化
  init();
});