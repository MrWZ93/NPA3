    def set_data(self, data, channel_names=None, channel_data=None):
        """设置要拟合的数据"""
        self.channel_combo.clear()
        
        if channel_names and len(channel_names) > 0:
            self.channel_combo.addItems(channel_names)
            self.channel_data = channel_data
            # 自动选择第一个通道
            self.on_channel_changed(0)
            # 启用拟合按钮
            self.fit_button.setEnabled(True)
        else:
            # 禁用拟合按钮
            self.fit_button.setEnabled(False)
    
    def on_channel_changed(self, index):
        """通道选择变更处理"""
        if index < 0 or not hasattr(self, "channel_data") or not self.channel_data:
            return
        
        # 获取选中通道的数据
        channel_name = self.channel_combo.currentText()
        if channel_name in self.channel_data:
            y_data = self.channel_data[channel_name]
            x_data = np.arange(len(y_data))
            
            # 更新范围选择器的最大值
            max_idx = len(y_data) - 1
            self.start_idx_spin.setMaximum(max_idx)
            self.end_idx_spin.setMaximum(max_idx)
            
            # 设置默认范围为全部数据
            self.start_idx_spin.setValue(0)
            self.end_idx_spin.setValue(max_idx)
            
            # 存储当前数据
            self.full_x_data = x_data
            self.full_y_data = y_data
            
            # 更新数据点信息
            self.points_value.setText(str(len(y_data)))
            
            # 更新预览图
            self.update_data_preview()
    
    def on_range_changed(self):
        """数据范围变更处理"""
        self.update_data_preview()
    
    def update_data_preview(self):
        """更新数据预览"""
        if not hasattr(self, "full_x_data") or not hasattr(self, "full_y_data"):
            return
        
        # 获取选定范围
        start_idx = self.start_idx_spin.value()
        end_idx = self.end_idx_spin.value()
        
        # 确保范围有效
        if start_idx >= end_idx:
            end_idx = start_idx + 1
            self.end_idx_spin.setValue(end_idx)
        
        # 选取数据
        self.x_data = self.full_x_data[start_idx:end_idx+1]
        self.y_data = self.full_y_data[start_idx:end_idx+1]
        
        # 更新点数信息
        self.points_value.setText(str(len(self.x_data)))
        
        # 更新预览图
        self.data_preview.plot_fit(self.x_data, self.y_data, title="数据预览")
    
    def on_model_changed(self, index):
        """模型选择变更处理"""
        model_name = self.model_combo.currentText()
        
        if model_name == "请选择...":
            self.params_group.setVisible(False)
            return
        
        # 显示或隐藏多项式阶数选择器
        is_poly = model_name == "多项式拟合"
        self.poly_order_label.setVisible(is_poly)
        self.poly_order_spin.setVisible(is_poly)
        
        if is_poly:
            # 更新多项式参数
            order = self.poly_order_spin.value()
            self.update_polynomial_params(order)
            
            # 连接阶数变化事件
            self.poly_order_spin.valueChanged.connect(self.on_poly_order_changed)
        
        # 创建参数控件
        self.create_param_controls(model_name)
    
    def on_poly_order_changed(self, order):
        """多项式阶数变更处理"""
        self.update_polynomial_params(order)
        self.create_param_controls("多项式拟合")
