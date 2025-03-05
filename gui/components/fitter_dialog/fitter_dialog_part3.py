    # 模型函数定义
    @staticmethod
    def linear_model(x, a=1.0, b=0.0):
        """线性模型: y = a*x + b"""
        return a * x + b
    
    @staticmethod
    def polynomial_model(x, **params):
        """多项式模型"""
        result = 0
        for name, value in params.items():
            if name.startswith('a'):
                try:
                    power = int(name[1:])
                    result += value * (x ** power)
                except ValueError:
                    pass
        return result
    
    @staticmethod
    def gaussian_model(x, a=1.0, b=0.0, c=1.0, d=0.0):
        """高斯模型: y = a*exp(-((x-b)/c)^2) + d"""
        return a * np.exp(-((x - b) / c) ** 2) + d
    
    @staticmethod
    def exponential_model(x, a=1.0, b=0.1, c=0.0):
        """指数模型: y = a*exp(b*x) + c"""
        return a * np.exp(b * x) + c
    
    @staticmethod
    def logarithmic_model(x, a=1.0, b=0.0):
        """对数模型: y = a*ln(x) + b"""
        # 处理x <= 0的情况
        mask = x > 0
        result = np.zeros_like(x, dtype=float)
        result[mask] = a * np.log(x[mask]) + b
        return result
    
    @staticmethod
    def power_model(x, a=1.0, b=1.0, c=0.0):
        """幂函数模型: y = a*x^b + c"""
        # 处理x < 0且b非整数的情况
        mask = x >= 0
        result = np.zeros_like(x, dtype=float)
        result[mask] = a * (x[mask] ** b) + c
        return result
    
    @staticmethod
    def tanh_model(x, a=1.0, b=1.0, c=0.0, d=0.0):
        """双曲正切模型: y = a*tanh(b*(x-c)) + d"""
        return a * np.tanh(b * (x - c)) + d
    
    @staticmethod
    def lorentzian_model(x, a=1.0, b=0.0, c=1.0, d=0.0):
        """洛伦兹模型: y = a/((x-b)^2 + c) + d"""
        return a / ((x - b) ** 2 + c) + d
    
    @staticmethod
    def sigmoid_model(x, a=1.0, b=1.0, c=0.0, d=0.0):
        """S型函数模型: y = a/(1+exp(-b*(x-c))) + d"""
        return a / (1 + np.exp(-b * (x - c))) + d