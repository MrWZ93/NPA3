    def perform_fit(self):
        """执行拟合"""
        if self.x_data is None or self.y_data is None or len(self.x_data) < 2:
            QMessageBox.warning(self, "错误", "没有足够的数据点进行拟合")
            return
        
        model_name = self.model_combo.currentText()
        if model_name == "请选择...":
            QMessageBox.warning(self, "错误", "请选择拟合模型")
            return
        
        # 获取模型函数
        model_func = self.model_functions.get(model_name)
        if not model_func:
            QMessageBox.warning(self, "错误", "不支持的拟合模型")
            return
        
        # 获取参数和边界
        init_params, bounds, fixed_params = self.get_current_param_values()
        
        # 创建拟合目标函数
        def objective(x, **params):
            # 合并固定参数
            for name, value in fixed_params.items():
                params[name] = value
            return model_func(x, **params)
        
        # 处理固定参数
        free_params = {k: v for k, v in init_params.items() if k not in fixed_params}
        free_bounds = {k: v for k, v in bounds.items() if k not in fixed_params}
        
        try:
            # 准备拟合参数
            p0 = list(free_params.values())
            param_names = list(free_params.keys())
            
            # 准备边界
            lower_bounds = []
            upper_bounds = []
            for param in param_names:
                lower, upper = free_bounds.get(param, (None, None))
                lower_bounds.append(-np.inf if lower is None else lower)
                upper_bounds.append(np.inf if upper is None else upper)
            
            # 特殊模型处理
            if model_name == "对数拟合 (y = a*ln(x) + b)":
                # 筛选x > 0的数据点
                mask = self.x_data > 0
                if np.sum(mask) < 2:
                    QMessageBox.warning(self, "错误", "对数拟合需要至少两个x > 0的数据点")
                    return
                x_fit = self.x_data[mask]
                y_fit = self.y_data[mask]
            elif model_name == "幂函数拟合 (y = a*x^b + c)":
                # 筛选x >= 0的数据点
                mask = self.x_data >= 0
                if np.sum(mask) < 2:
                    QMessageBox.warning(self, "错误", "幂函数拟合需要至少两个x >= 0的数据点")
                    return
                x_fit = self.x_data[mask]
                y_fit = self.y_data[mask]
            else:
                x_fit = self.x_data
                y_fit = self.y_data
            
            # 执行曲线拟合
            if not param_names:  # 如果所有参数都固定
                popt = []
                pcov = np.zeros((0, 0))
                fit_result = lambda x: objective(x, **fixed_params)
            else:
                popt, pcov = optimize.curve_fit(
                    lambda x, *args: objective(x, **dict(zip(param_names, args))),
                    x_fit, y_fit, p0=p0, bounds=(lower_bounds, upper_bounds)
                )
                # 创建拟合结果函数
                fit_params = dict(zip(param_names, popt))
                fit_params.update(fixed_params)
                fit_result = lambda x: objective(x, **fit_params)
            
            # 获取拟合参数和误差
            fit_params = {}
            fit_errors = {}
            
            # 添加自由参数和误差
            for i, param in enumerate(param_names):
                fit_params[param] = popt[i]
                if pcov.size > 0:  # 确保协方差矩阵不为空
                    try:
                        fit_errors[param] = np.sqrt(np.diag(pcov))[i]
                    except:
                        fit_errors[param] = np.nan
            
            # 添加固定参数
            for param, value in fixed_params.items():
                fit_params[param] = value
            
            # 计算拟合统计信息
            y_fit_pred = fit_result(x_fit)
            residuals = y_fit - y_fit_pred
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y_fit - np.mean(y_fit)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            rmse = np.sqrt(np.mean(residuals ** 2))
            
            # 生成拟合曲线数据用于绘图
            if model_name in ["对数拟合 (y = a*ln(x) + b)", "幂函数拟合 (y = a*x^b + c)"]:
                # 对于这些特殊模型，生成在有效域上的曲线
                fit_x = np.linspace(max(0.001, min(x_fit)), max(x_fit), 1000)
            else:
                fit_x = np.linspace(min(self.x_data), max(self.x_data), 1000)
            
            fit_y = fit_result(fit_x)
            
            # 更新拟合结果显示
            self.fit_plot.plot_fit(
                self.x_data, self.y_data,
                fit_x=fit_x, fit_y=fit_y,
                title=f"拟合结果 - {model_name}"
            )
            
            # 更新结果表格
            self.results_table.update_fit_results(fit_params, fit_errors, bounds)
            
            # 更新统计信息
            stats_text = f"R² = {r_squared:.6f}, RMSE = {rmse:.6g}"
            self.fit_stats_value.setText(stats_text)
            
            # 存储拟合结果
            self.fit_result = {
                "model": model_name,
                "params": fit_params,
                "errors": fit_errors,
                "r_squared": r_squared,
                "rmse": rmse,
                "fit_x": fit_x,
                "fit_y": fit_y
            }
            
            # 启用导出和复制按钮
            self.export_button.setEnabled(True)
            self.copy_button.setEnabled(True)
            
            # 切换到结果标签页
            self.tabs.setCurrentIndex(1)
            
        except Exception as e:
            QMessageBox.critical(self, "拟合错误", f"拟合过程中发生错误:\n{str(e)}")
    
    def export_results(self):
        """导出拟合结果"""
        if not self.fit_result:
            return
        
        # TODO: 实现结果导出功能
        QMessageBox.information(self, "导出结果", "导出功能待实现")
    
    def copy_params(self):
        """复制拟合参数到剪贴板"""
        if not self.fit_result:
            return
        
        params = self.fit_result["params"]
        text = f"模型: {self.fit_result['model']}\n"
        text += f"R²: {self.fit_result['r_squared']:.6f}\n"
        text += f"RMSE: {self.fit_result['rmse']:.6g}\n\n"
        text += "参数:\n"
        
        for name, value in params.items():
            if name in self.fit_result["errors"]:
                error = self.fit_result["errors"][name]
                text += f"{name} = {value:.6g} ± {error:.6g}\n"
            else:
                text += f"{name} = {value:.6g} (fixed)\n"
        
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "复制成功", "参数已复制到剪贴板")
