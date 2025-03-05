    def initialize_models(self):
        """初始化模型函数和参数"""
        # 模型函数字典
        self.model_functions = {
            "线性拟合 (y = a*x + b)": self.linear_model,
            "多项式拟合": self.polynomial_model,
            "高斯拟合 (y = a*exp(-((x-b)/c)^2) + d)": self.gaussian_model,
            "指数拟合 (y = a*exp(b*x) + c)": self.exponential_model,
            "对数拟合 (y = a*ln(x) + b)": self.logarithmic_model,
            "幂函数拟合 (y = a*x^b + c)": self.power_model,
            "双曲正切拟合 (y = a*tanh(b*(x-c)) + d)": self.tanh_model,
            "洛伦兹拟合 (y = a/((x-b)^2 + c) + d)": self.lorentzian_model,
            "S型函数拟合 (y = a/(1+exp(-b*(x-c))) + d)": self.sigmoid_model
        }
        
        # 初始化模型参数和边界
        self.model_params = {
            "线性拟合 (y = a*x + b)": {
                "params": {"a": 1.0, "b": 0.0},
                "bounds": {"a": (None, None), "b": (None, None)},
                "descriptions": {
                    "a": "斜率",
                    "b": "截距"
                }
            },
            "多项式拟合": {},  # 根据选择的阶数动态生成
            "高斯拟合 (y = a*exp(-((x-b)/c)^2) + d)": {
                "params": {"a": 1.0, "b": 0.0, "c": 1.0, "d": 0.0},
                "bounds": {"a": (None, None), "b": (None, None), "c": (0.01, None), "d": (None, None)},
                "descriptions": {
                    "a": "振幅",
                    "b": "中心位置",
                    "c": "宽度",
                    "d": "偏移量"
                }
            },
            "指数拟合 (y = a*exp(b*x) + c)": {
                "params": {"a": 1.0, "b": 0.1, "c": 0.0},
                "bounds": {"a": (None, None), "b": (None, None), "c": (None, None)},
                "descriptions": {
                    "a": "振幅",
                    "b": "指数系数",
                    "c": "偏移量"
                }
            },
            "对数拟合 (y = a*ln(x) + b)": {
                "params": {"a": 1.0, "b": 0.0},
                "bounds": {"a": (None, None), "b": (None, None)},
                "descriptions": {
                    "a": "系数",
                    "b": "偏移量"
                }
            },
            "幂函数拟合 (y = a*x^b + c)": {
                "params": {"a": 1.0, "b": 1.0, "c": 0.0},
                "bounds": {"a": (None, None), "b": (None, None), "c": (None, None)},
                "descriptions": {
                    "a": "系数",
                    "b": "幂",
                    "c": "偏移量"
                }
            },
            "双曲正切拟合 (y = a*tanh(b*(x-c)) + d)": {
                "params": {"a": 1.0, "b": 1.0, "c": 0.0, "d": 0.0},
                "bounds": {"a": (None, None), "b": (None, None), "c": (None, None), "d": (None, None)},
                "descriptions": {
                    "a": "振幅",
                    "b": "速率",
                    "c": "中心位置",
                    "d": "偏移量"
                }
            },
            "洛伦兹拟合 (y = a/((x-b)^2 + c) + d)": {
                "params": {"a": 1.0, "b": 0.0, "c": 1.0, "d": 0.0},
                "bounds": {"a": (None, None), "b": (None, None), "c": (0.01, None), "d": (None, None)},
                "descriptions": {
                    "a": "振幅",
                    "b": "中心位置",
                    "c": "宽度",
                    "d": "偏移量"
                }
            },
            "S型函数拟合 (y = a/(1+exp(-b*(x-c))) + d)": {
                "params": {"a": 1.0, "b": 1.0, "c": 0.0, "d": 0.0},
                "bounds": {"a": (None, None), "b": (None, None), "c": (None, None), "d": (None, None)},
                "descriptions": {
                    "a": "振幅",
                    "b": "速率",
                    "c": "中心位置",
                    "d": "偏移量"
                }
            }
        }
        
        # 设置多项式参数
        self.update_polynomial_params(2)  # 默认二阶多项式
        
        # 参数控件
        self.param_controls = {}
    
    def update_polynomial_params(self, order):
        """更新多项式参数"""
        params = {}
        bounds = {}
        descriptions = {}
        
        for i in range(order + 1):
            param_name = f"a{i}"
            params[param_name] = 1.0 if i == 1 else 0.0  # a1默认为1，其他为0
            bounds[param_name] = (None, None)
            
            if i == 0:
                descriptions[param_name] = "常数项"
            elif i == 1:
                descriptions[param_name] = "一次项系数"
            else:
                descriptions[param_name] = f"{i}次项系数"
        
        self.model_params["多项式拟合"] = {
            "params": params,
            "bounds": bounds,
            "descriptions": descriptions,
            "order": order
        }
    
    def create_param_controls(self, model_name):
        """创建模型参数的控制组件"""
        # 清除现有控件
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.param_controls = {}
        
        if model_name not in self.model_params:
            self.params_group.setVisible(False)
            return
        
        # 获取模型参数
        model_info = self.model_params[model_name]
        params = model_info["params"]
        bounds = model_info["bounds"]
        descriptions = model_info.get("descriptions", {})
        
        if not params:
            self.params_group.setVisible(False)
            return
        
        # 创建标题行
        self.params_layout.addWidget(QLabel("参数名称"), 0, 0)
        self.params_layout.addWidget(QLabel("描述"), 0, 1)
        self.params_layout.addWidget(QLabel("初始值"), 0, 2)
        self.params_layout.addWidget(QLabel("下限"), 0, 3)
        self.params_layout.addWidget(QLabel("上限"), 0, 4)
        self.params_layout.addWidget(QLabel("固定"), 0, 5)
        
        # 为每个参数创建控件
        row = 1
        for param_name, value in params.items():
            # 参数名
            name_label = QLabel(param_name)
            self.params_layout.addWidget(name_label, row, 0)
            
            # 描述
            desc = descriptions.get(param_name, "")
            desc_label = QLabel(desc)
            self.params_layout.addWidget(desc_label, row, 1)
            
            # 初始值
            value_spin = QDoubleSpinBox()
            value_spin.setRange(-1e6, 1e6)
            value_spin.setDecimals(6)
            value_spin.setValue(value)
            value_spin.setSingleStep(0.1)
            self.params_layout.addWidget(value_spin, row, 2)
            
            # 下限
            min_spin = QDoubleSpinBox()
            min_spin.setRange(-1e6, 1e6)
            min_spin.setDecimals(6)
            min_spin.setSpecialValueText("None")
            min_bound = bounds.get(param_name, (None, None))[0]
            if min_bound is not None:
                min_spin.setValue(min_bound)
            else:
                min_spin.setValue(min_spin.minimum())
            self.params_layout.addWidget(min_spin, row, 3)
            
            # 上限
            max_spin = QDoubleSpinBox()
            max_spin.setRange(-1e6, 1e6)
            max_spin.setDecimals(6)
            max_spin.setSpecialValueText("None")
            max_bound = bounds.get(param_name, (None, None))[1]
            if max_bound is not None:
                max_spin.setValue(max_bound)
            else:
                max_spin.setValue(max_spin.maximum())
            self.params_layout.addWidget(max_spin, row, 4)
            
            # 固定参数复选框
            fixed_check = QCheckBox()
            self.params_layout.addWidget(fixed_check, row, 5)
            
            # 存储控件引用
            self.param_controls[param_name] = {
                "value": value_spin,
                "min": min_spin,
                "max": max_spin,
                "fixed": fixed_check
            }
            
            row += 1
        
        self.params_group.setVisible(True)
    
    def get_current_param_values(self):
        """获取当前参数值和边界"""
        params = {}
        bounds = {}
        fixed_params = {}
        
        for param_name, controls in self.param_controls.items():
            # 参数值
            params[param_name] = controls["value"].value()
            
            # 边界
            min_val = controls["min"].value()
            max_val = controls["max"].value()
            
            # 检查是否为特殊值（None）
            if min_val == controls["min"].minimum():
                min_val = None
            if max_val == controls["max"].maximum():
                max_val = None
            
            bounds[param_name] = (min_val, max_val)
            
            # 固定参数
            if controls["fixed"].isChecked():
                fixed_params[param_name] = params[param_name]
        
        return params, bounds, fixed_params