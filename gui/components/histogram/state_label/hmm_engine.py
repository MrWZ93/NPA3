#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HMM State Analyzer Engine
-------------------------

适用于一维台阶信号的固定参数 Gaussian-HMM + Log-Viterbi 解码器。

核心特点与改进：
1. 跨越状态越多，转移概率越低（Jump Decay 跨级惩罚）；
2. 自转移概率可根据实际采样率 (sampling_rate) 和期望停留时间 (expected_dwell_ms) 物理计算；
3. 防止宽 sigma 的高状态吸收低电平过渡点与边缘噪声点；
4. 约束合并低于最小停留时间 (minimum dwell time) 的单点或极短假状态；
5. 输出原始路径与清理后的理想化阶梯轨迹；
6. 输出 State-to-State Transition Counts 与 Transition Rates (s^-1) 转换速率矩阵；
7. 100% 兼容旧版本 UI 与导出接口。
"""

import numpy as np


class HMMStateAnalyzer:
    """一维 Gaussian-HMM 状态分析器。"""

    COLOR_PALETTE = [
        "#e74c3c",
        "#2ecc71",
        "#3498db",
        "#f39c12",
        "#9b59b6",
        "#1abc9c",
        "#d35400",
        "#34495e",
        "#e67e22",
        "#7f8c8d",
    ]

    # ============================================================
    # 自动猜测参数
    # ============================================================

    @staticmethod
    def auto_guess_parameters(data, num_states=2):
        """
        根据数据分位数粗略估计各状态的 mean 和 std。

        对正式分析，建议使用 histogram Gaussian fitting 得到的 mean/std。
        """
        if data is None:
            return []

        x = np.asarray(data, dtype=np.float64).reshape(-1)
        x = x[np.isfinite(x)]

        if len(x) == 0:
            return []

        num_states = int(np.clip(num_states, 2, 50))

        quantiles = np.linspace(0, 100, num_states + 1)
        edges = np.percentile(x, quantiles)

        overall_std = max(float(np.std(x)), 1e-8)
        params = []

        for i in range(num_states):
            low = edges[i]
            high = edges[i + 1]

            if i == num_states - 1:
                subset = x[(x >= low) & (x <= high)]
            else:
                subset = x[(x >= low) & (x < high)]

            if len(subset) >= 3:
                mean_value = float(np.mean(subset))

                # 使用 MAD 避免少量大幅变化把 sigma 拉得过宽
                median = float(np.median(subset))
                mad_sigma = (
                    1.4826
                    * float(np.median(np.abs(subset - median)))
                )

                normal_std = float(np.std(subset))

                if mad_sigma > 0:
                    std_value = min(
                        normal_std,
                        mad_sigma * 1.5,
                    )
                else:
                    std_value = normal_std

            else:
                mean_value = float((low + high) / 2.0)
                std_value = overall_std / num_states

            std_value = max(
                std_value,
                overall_std * 1e-3,
                1e-8,
            )

            params.append(
                {
                    "id": i,
                    "name": f"State {i + 1}",
                    "mean": round(mean_value, 6),
                    "std": round(std_value, 6),
                    "color": HMMStateAnalyzer.COLOR_PALETTE[
                        i % len(HMMStateAnalyzer.COLOR_PALETTE)
                    ],
                }
            )

        params.sort(key=lambda item: item["mean"])

        for i, item in enumerate(params):
            item["id"] = i
            item["name"] = f"State {i + 1}"

        return params

    # ============================================================
    # 主解码函数
    # ============================================================

    @staticmethod
    def decode_states(
        data,
        state_params,
        self_trans_prob=None,
        sampling_rate=1000.0,
        expected_dwell_ms=1.0,
        jump_decay=2.0,
        amplitude_distance_weight=0.0,
        min_dwell_ms=0.25,
        clean_short_events=True,
        emission_gate_z=6.0,
        boundary_margin_sigma=1.5,
        max_sigma_fraction=0.45,
        min_sigma=None,
    ):
        """
        固定 state mean/std，使用 Log-Viterbi 解码状态路径。

        Parameters
        ----------
        data : 1D array
            原始电流或电导时间序列。

        state_params : list of dict
            每个状态至少包含：
            {
                "mean": float,
                "std": float
            }

        self_trans_prob : float、list 或 None
            自转移概率。推荐设为 None，让程序根据 sampling_rate 和 expected_dwell_ms 自动计算。

        sampling_rate : float
            实际数据采样率 Hz。

        expected_dwell_ms : float 或 list
            对状态平均 dwell time 的初始估计（ms）。

        jump_decay : float
            跨级转换惩罚强度。推荐：1.5～3.0，默认 2.0。

        min_dwell_ms : float
            最短有效状态持续时间（ms）。低于该时间的状态片段会合并到前后状态。

        Returns
        -------
        dict
            path, raw_path, fitted_trace, raw_fitted_trace, stats, transition_counts, transition_rates_per_s 等。
        """

        if data is None or not state_params:
            return None

        x = HMMStateAnalyzer._prepare_data(data)

        if len(x) == 0:
            return None

        sampling_rate = float(sampling_rate)

        if (
            not np.isfinite(sampling_rate)
            or sampling_rate <= 0
        ):
            raise ValueError(
                "sampling_rate 必须是实际采样率，并且大于 0。"
            )

        # 状态必须按 mean 递增排列
        sorted_params = sorted(
            [dict(item) for item in state_params],
            key=lambda item: float(item["mean"]),
        )

        num_states = len(sorted_params)
        num_points = len(x)

        means = np.array(
            [
                float(item["mean"])
                for item in sorted_params
            ],
            dtype=np.float64,
        )

        raw_stds = np.array(
            [
                max(float(item["std"]), 1e-12)
                for item in sorted_params
            ],
            dtype=np.float64,
        )

        if np.any(~np.isfinite(means)):
            raise ValueError("State mean 中存在无效数值。")

        if np.any(~np.isfinite(raw_stds)):
            raise ValueError("State std 中存在无效数值。")

        if np.any(np.diff(means) <= 0):
            raise ValueError(
                "不同状态的 mean 必须严格递增，不能相同。"
            )

        # --------------------------------------------------------
        # 1. 限制过宽 sigma
        # --------------------------------------------------------

        effective_stds, nearest_spacing = (
            HMMStateAnalyzer._sanitize_sigmas(
                data=x,
                means=means,
                raw_stds=raw_stds,
                max_sigma_fraction=max_sigma_fraction,
                min_sigma=min_sigma,
            )
        )

        # --------------------------------------------------------
        # 2. 构建 Gaussian emission probability
        # --------------------------------------------------------

        log_emission = (
            HMMStateAnalyzer._build_log_emission(
                data=x,
                means=means,
                stds=effective_stds,
                nearest_spacing=nearest_spacing,
                emission_gate_z=emission_gate_z,
                boundary_margin_sigma=boundary_margin_sigma,
            )
        )

        # --------------------------------------------------------
        # 3. 构建距离敏感的 transition matrix
        # --------------------------------------------------------

        transition_matrix = (
            HMMStateAnalyzer._build_transition_matrix(
                means=means,
                sampling_rate=sampling_rate,
                expected_dwell_ms=expected_dwell_ms,
                self_trans_prob=self_trans_prob,
                jump_decay=jump_decay,
                amplitude_distance_weight=amplitude_distance_weight,
            )
        )

        log_transition = np.log(
            np.maximum(transition_matrix, 1e-300)
        )

        # 初始状态概率先设均匀分布
        start_probability = np.full(
            num_states,
            1.0 / num_states,
            dtype=np.float64,
        )

        # --------------------------------------------------------
        # 4. Viterbi 解码
        # --------------------------------------------------------

        raw_path, path_score = (
            HMMStateAnalyzer._viterbi(
                log_emission=log_emission,
                log_transition=log_transition,
                log_start=np.log(start_probability),
            )
        )

        # --------------------------------------------------------
        # 5. 清理极短状态
        # --------------------------------------------------------

        minimum_samples = max(
            1,
            int(
                np.ceil(
                    min_dwell_ms
                    * 1e-3
                    * sampling_rate
                )
            ),
        )

        if (
            clean_short_events
            and min_dwell_ms > 0
        ):
            cleaned_path, cleanup_info = (
                HMMStateAnalyzer._merge_short_runs(
                    path=raw_path,
                    log_emission=log_emission,
                    log_transition=log_transition,
                    minimum_samples=minimum_samples,
                )
            )
        else:
            cleaned_path = raw_path.copy()

            cleanup_info = {
                "iterations": 0,
                "runs_modified": 0,
                "samples_modified": 0,
            }

        raw_fitted_trace = means[raw_path]
        fitted_trace = means[cleaned_path]

        # --------------------------------------------------------
        # 6. 统计
        # --------------------------------------------------------

        stats = HMMStateAnalyzer._compute_stats(
            path=cleaned_path,
            state_params=sorted_params,
            sampling_rate=sampling_rate,
        )

        transition_counts, transition_rates = (
            HMMStateAnalyzer._compute_transition_matrices(
                path=cleaned_path,
                num_states=num_states,
                sampling_rate=sampling_rate,
            )
        )

        return {
            # 保持主字段 100% 兼容
            "path": cleaned_path,
            "fitted_trace": fitted_trace,
            "stats": stats,
            "total_duration_sec": (
                num_points / sampling_rate
            ),
            "sampling_rate": sampling_rate,
            "total_points": num_points,

            # 扩展动力学与算法分析字段
            "raw_path": raw_path,
            "raw_fitted_trace": raw_fitted_trace,
            "transition_matrix_prior": (
                transition_matrix
            ),
            "transition_counts": transition_counts,
            "transition_rates_per_s": (
                transition_rates
            ),
            "means": means,
            "raw_stds": raw_stds,
            "effective_stds": effective_stds,
            "nearest_spacing": nearest_spacing,
            "path_log_score": float(path_score),
            "cleanup_info": cleanup_info,
            "min_dwell_samples": minimum_samples,
            "min_dwell_ms": float(min_dwell_ms),
            "sorted_state_params": sorted_params,
        }

    # ============================================================
    # 数据准备
    # ============================================================

    @staticmethod
    def _prepare_data(data):
        """转换为一维 float array，并插值少量 NaN/Inf。"""

        x = np.asarray(
            data,
            dtype=np.float64,
        ).reshape(-1)

        if len(x) == 0:
            return x

        valid = np.isfinite(x)

        if np.all(valid):
            return x

        if np.sum(valid) < 2:
            raise ValueError(
                "有效数据点不足，无法进行插值。"
            )

        indices = np.arange(len(x))

        x = x.copy()

        x[~valid] = np.interp(
            indices[~valid],
            indices[valid],
            x[valid],
        )

        return x

    # ============================================================
    # Sigma 限制
    # ============================================================

    @staticmethod
    def _sanitize_sigmas(
        data,
        means,
        raw_stds,
        max_sigma_fraction,
        min_sigma,
    ):
        """
        限制过宽的 sigma，防止高状态充当 catch-all state。
        """

        num_states = len(means)

        if num_states == 1:
            nearest_spacing = np.array(
                [
                    max(
                        float(np.std(data)),
                        1e-6,
                    )
                ],
                dtype=np.float64,
            )

        else:
            state_differences = np.diff(means)

            nearest_spacing = np.empty(
                num_states,
                dtype=np.float64,
            )

            nearest_spacing[0] = (
                state_differences[0]
            )

            nearest_spacing[-1] = (
                state_differences[-1]
            )

            if num_states > 2:
                nearest_spacing[1:-1] = np.minimum(
                    state_differences[:-1],
                    state_differences[1:],
                )

        data_scale = max(
            float(np.std(data)),
            float(np.ptp(data)) * 1e-4,
            1e-8,
        )

        if min_sigma is None:
            sigma_floor = max(
                data_scale * 1e-3,
                1e-8,
            )
        else:
            sigma_floor = max(
                float(min_sigma),
                1e-12,
            )

        max_sigma_fraction = float(
            np.clip(
                max_sigma_fraction,
                0.05,
                2.0,
            )
        )

        sigma_ceiling = np.maximum(
            nearest_spacing
            * max_sigma_fraction,
            sigma_floor,
        )

        effective_stds = np.clip(
            raw_stds,
            sigma_floor,
            sigma_ceiling,
        )

        return effective_stds, nearest_spacing

    # ============================================================
    # Gaussian emission
    # ============================================================

    @staticmethod
    def _build_log_emission(
        data,
        means,
        stds,
        nearest_spacing,
        emission_gate_z,
        boundary_margin_sigma,
    ):
        """
        构建 Gaussian log-emission。
        除高斯概率外，还使用相邻 mean 的中点建立软边界。
        """

        difference = (
            data[:, None]
            - means[None, :]
        )

        variance = stds ** 2

        log_emission = (
            -0.5 * np.log(2.0 * np.pi)
            - np.log(stds)[None, :]
            - (difference ** 2)
            / (2.0 * variance[None, :])
        )

        num_states = len(means)

        if num_states == 1:
            return log_emission

        # 相邻状态 mean 的中点
        midpoints = (
            means[:-1]
            + means[1:]
        ) / 2.0

        lower_bound = np.full(
            num_states,
            -np.inf,
            dtype=np.float64,
        )

        upper_bound = np.full(
            num_states,
            np.inf,
            dtype=np.float64,
        )

        lower_bound[1:] = midpoints
        upper_bound[:-1] = midpoints

        # 允许边界向外扩展一定范围
        margin = np.maximum(
            boundary_margin_sigma * stds,
            0.10 * nearest_spacing,
        )

        lower_soft = lower_bound - margin
        upper_soft = upper_bound + margin

        outside_boundary = (
            (
                data[:, None]
                < lower_soft[None, :]
            )
            |
            (
                data[:, None]
                > upper_soft[None, :]
            )
        )

        z_score = (
            np.abs(difference)
            / stds[None, :]
        )

        outside_z = (
            z_score
            > max(float(emission_gate_z), 1.0)
        )

        # 施加强惩罚 (-80.0)，避免误划分与路径断裂
        invalid_assignment = (
            outside_boundary
            | outside_z
        )

        log_emission = (
            log_emission
            - invalid_assignment * 80.0
        )

        return log_emission

    # ============================================================
    # Transition matrix
    # ============================================================

    @staticmethod
    def _build_transition_matrix(
        means,
        sampling_rate,
        expected_dwell_ms,
        self_trans_prob,
        jump_decay,
        amplitude_distance_weight,
    ):
        """
        构建跨级距离敏感的 transition matrix。
        P(i -> j) 与 exp(-jump_decay * |i-j|) 成比例。
        """

        num_states = len(means)

        if num_states == 1:
            return np.ones(
                (1, 1),
                dtype=np.float64,
            )

        dt = 1.0 / sampling_rate

        # 根据 dwell time 自动计算 self-transition
        if self_trans_prob is None:
            dwell_values = (
                HMMStateAnalyzer._to_state_vector(
                    expected_dwell_ms,
                    num_states,
                    "expected_dwell_ms",
                )
            )

            if np.any(dwell_values <= 0):
                raise ValueError(
                    "expected_dwell_ms 必须大于 0。"
                )

            dwell_seconds = (
                dwell_values * 1e-3
            )

            stay_probability = np.exp(
                -dt / dwell_seconds
            )

        else:
            stay_probability = (
                HMMStateAnalyzer._to_state_vector(
                    self_trans_prob,
                    num_states,
                    "self_trans_prob",
                )
            )

        stay_probability = np.clip(
            stay_probability,
            0.50,
            0.999999999,
        )

        state_indices = np.arange(
            num_states,
        )

        index_distance = np.abs(
            state_indices[:, None]
            - state_indices[None, :]
        ).astype(np.float64)

        # 跨越状态越多，先验权重越小
        transition_weights = np.exp(
            -max(float(jump_decay), 0.0)
            * index_distance
        )

        if amplitude_distance_weight > 0:
            amplitude_distance = np.abs(
                means[:, None]
                - means[None, :]
            )

            median_spacing = max(
                float(np.median(np.diff(means))),
                1e-12,
            )

            transition_weights *= np.exp(
                -float(
                    amplitude_distance_weight
                )
                * amplitude_distance
                / median_spacing
            )

        np.fill_diagonal(
            transition_weights,
            0.0,
        )

        transition_matrix = np.zeros(
            (num_states, num_states),
            dtype=np.float64,
        )

        for i in range(num_states):
            weights = (
                transition_weights[i].copy()
            )

            weight_sum = float(
                np.sum(weights)
            )

            if weight_sum <= 0:
                weights[:] = 1.0
                weights[i] = 0.0
                weight_sum = float(
                    np.sum(weights)
                )

            transition_matrix[i] = (
                (1.0 - stay_probability[i])
                * weights
                / weight_sum
            )

            transition_matrix[i, i] = (
                stay_probability[i]
            )

        transition_matrix = np.maximum(
            transition_matrix,
            1e-300,
        )

        transition_matrix /= (
            transition_matrix.sum(
                axis=1,
                keepdims=True,
            )
        )

        return transition_matrix

    @staticmethod
    def _to_state_vector(
        value,
        num_states,
        parameter_name,
    ):
        """把标量或 list 转成长度为 K 的数组。"""

        array = np.asarray(
            value,
            dtype=np.float64,
        )

        if array.ndim == 0:
            return np.full(
                num_states,
                float(array),
                dtype=np.float64,
            )

        array = array.reshape(-1)

        if len(array) != num_states:
            raise ValueError(
                f"{parameter_name} 必须是标量，"
                f"或者长度为 {num_states} 的序列。"
            )

        return array

    # ============================================================
    # Viterbi
    # ============================================================

    @staticmethod
    def _viterbi(
        log_emission,
        log_transition,
        log_start,
    ):
        """标准 Log-Viterbi 动态规划。"""

        num_points, num_states = (
            log_emission.shape
        )

        score_matrix = np.empty(
            (num_points, num_states),
            dtype=np.float64,
        )

        back_pointer = np.zeros(
            (num_points, num_states),
            dtype=np.int32,
        )

        score_matrix[0] = (
            log_start
            + log_emission[0]
        )

        for t in range(1, num_points):
            candidate_scores = (
                score_matrix[t - 1][:, None]
                + log_transition
            )

            back_pointer[t] = np.argmax(
                candidate_scores,
                axis=0,
            )

            score_matrix[t] = (
                np.max(
                    candidate_scores,
                    axis=0,
                )
                + log_emission[t]
            )

        path = np.empty(
            num_points,
            dtype=np.int32,
        )

        path[-1] = int(
            np.argmax(score_matrix[-1])
        )

        for t in range(
            num_points - 2,
            -1,
            -1,
        ):
            path[t] = back_pointer[
                t + 1,
                path[t + 1],
            ]

        final_score = float(
            score_matrix[
                -1,
                path[-1],
            ]
        )

        return path, final_score

    # ============================================================
    # Run-length encoding
    # ============================================================

    @staticmethod
    def _run_length_encode(path):
        """返回：[(start, end_exclusive, state), ...]"""

        if len(path) == 0:
            return []

        boundaries = np.flatnonzero(
            np.r_[
                True,
                path[1:] != path[:-1],
                True,
            ]
        )

        runs = []

        for start, end in zip(
            boundaries[:-1],
            boundaries[1:],
        ):
            runs.append(
                (
                    int(start),
                    int(end),
                    int(path[start]),
                )
            )

        return runs

    # ============================================================
    # Minimum dwell time 清理
    # ============================================================

    @staticmethod
    def _merge_short_runs(
        path,
        log_emission,
        log_transition,
        minimum_samples,
        max_iterations=100,
    ):
        """
        清理低于 minimum_samples 的状态片段。
        对一个短片段，只允许合并到它的前一个或后一个状态。
        """

        cleaned_path = path.copy()

        runs_modified = 0
        samples_modified = 0

        if minimum_samples <= 1:
            return cleaned_path, {
                "iterations": 0,
                "runs_modified": 0,
                "samples_modified": 0,
            }

        for iteration in range(
            1,
            max_iterations + 1,
        ):
            runs = (
                HMMStateAnalyzer._run_length_encode(
                    cleaned_path
                )
            )

            changed = False

            for run_index, run in enumerate(runs):
                start, end, current_state = run

                run_length = end - start

                if run_length >= minimum_samples:
                    continue

                previous_state = (
                    runs[run_index - 1][2]
                    if run_index > 0
                    else None
                )

                next_state = (
                    runs[run_index + 1][2]
                    if run_index + 1 < len(runs)
                    else None
                )

                candidates = []

                if previous_state is not None:
                    candidates.append(
                        previous_state
                    )

                if (
                    next_state is not None
                    and next_state not in candidates
                ):
                    candidates.append(
                        next_state
                    )

                if not candidates:
                    continue

                best_state = current_state
                best_score = -np.inf

                for candidate_state in candidates:
                    score = float(
                        np.sum(
                            log_emission[
                                start:end,
                                candidate_state,
                            ]
                        )
                    )

                    if previous_state is not None:
                        score += float(
                            log_transition[
                                previous_state,
                                candidate_state,
                            ]
                        )

                    if next_state is not None:
                        score += float(
                            log_transition[
                                candidate_state,
                                next_state,
                            ]
                        )

                    if score > best_score:
                        best_score = score
                        best_state = candidate_state

                if best_state != current_state:
                    cleaned_path[start:end] = (
                        best_state
                    )

                    runs_modified += 1
                    samples_modified += (
                        run_length
                    )

                    changed = True

            if not changed:
                return cleaned_path, {
                    "iterations": iteration,
                    "runs_modified": runs_modified,
                    "samples_modified": (
                        samples_modified
                    ),
                }

        return cleaned_path, {
            "iterations": max_iterations,
            "runs_modified": runs_modified,
            "samples_modified": samples_modified,
        }

    # ============================================================
    # State statistics
    # ============================================================

    @staticmethod
    def _compute_stats(
        path,
        state_params,
        sampling_rate,
    ):
        """计算 occupancy、event 数和 dwell-time 指标。"""

        num_points = len(path)
        num_states = len(state_params)

        runs = HMMStateAnalyzer._run_length_encode(
            path
        )

        dwell_points_by_state = [
            []
            for _ in range(num_states)
        ]

        for start, end, state in runs:
            dwell_points_by_state[
                state
            ].append(end - start)

        stats = []

        for state_index in range(num_states):
            point_count = int(
                np.sum(path == state_index)
            )

            total_state_sec = (
                point_count
                / sampling_rate
            )

            dwell_points = np.asarray(
                dwell_points_by_state[
                    state_index
                ],
                dtype=np.float64,
            )

            num_events = len(dwell_points)

            if num_events > 0:
                average_dwell_points = float(
                    np.mean(dwell_points)
                )

                average_dwell_sec = (
                    average_dwell_points
                    / sampling_rate
                )

                median_dwell_ms = float(
                    np.median(dwell_points)
                    / sampling_rate
                    * 1000.0
                )

                minimum_dwell_ms = float(
                    np.min(dwell_points)
                    / sampling_rate
                    * 1000.0
                )

                maximum_dwell_ms = float(
                    np.max(dwell_points)
                    / sampling_rate
                    * 1000.0
                )

            else:
                average_dwell_points = 0.0
                average_dwell_sec = 0.0
                median_dwell_ms = 0.0
                minimum_dwell_ms = 0.0
                maximum_dwell_ms = 0.0

            item = state_params[state_index]

            stats.append(
                {
                    "id": state_index,
                    "name": item.get(
                        "name",
                        f"State {state_index + 1}",
                    ),
                    "mean": float(item["mean"]),
                    "std": float(item["std"]),
                    "color": item.get(
                        "color",
                        HMMStateAnalyzer.COLOR_PALETTE[
                            state_index
                            % len(
                                HMMStateAnalyzer.COLOR_PALETTE
                            )
                        ],
                    ),

                    "count_pts": point_count,

                    "total_state_sec": round(
                        total_state_sec,
                        6,
                    ),

                    "total_state_ms": round(
                        total_state_sec * 1000.0,
                        3,
                    ),

                    "occupancy_pct": round(
                        (
                            point_count
                            / num_points
                            * 100.0
                        )
                        if num_points > 0
                        else 0.0,
                        3,
                    ),

                    "num_events": num_events,

                    "avg_dwell_pts": round(
                        average_dwell_points,
                        3,
                    ),

                    "avg_dwell_sec": round(
                        average_dwell_sec,
                        6,
                    ),

                    "avg_dwell_ms": round(
                        average_dwell_sec
                        * 1000.0,
                        3,
                    ),

                    "median_dwell_ms": round(
                        median_dwell_ms,
                        3,
                    ),

                    "min_dwell_ms": round(
                        minimum_dwell_ms,
                        3,
                    ),

                    "max_dwell_ms": round(
                        maximum_dwell_ms,
                        3,
                    ),
                }
            )

        return stats

    # ============================================================
    # Transition statistics
    # ============================================================

    @staticmethod
    def _compute_transition_matrices(
        path,
        num_states,
        sampling_rate,
    ):
        """
        计算 event-level transition counts 和 rates。
        rate[i, j] = N(i -> j) / total_time_in_state_i (s^-1)
        """

        runs = HMMStateAnalyzer._run_length_encode(
            path
        )

        event_states = np.array(
            [
                state
                for _, _, state in runs
            ],
            dtype=np.int32,
        )

        transition_counts = np.zeros(
            (num_states, num_states),
            dtype=np.int64,
        )

        for from_state, to_state in zip(
            event_states[:-1],
            event_states[1:],
        ):
            transition_counts[
                from_state,
                to_state,
            ] += 1

        total_time_by_state = np.array(
            [
                np.sum(path == state_index)
                / sampling_rate
                for state_index
                in range(num_states)
            ],
            dtype=np.float64,
        )

        transition_rates = np.divide(
            transition_counts,
            total_time_by_state[:, None],
            out=np.zeros(
                transition_counts.shape,
                dtype=np.float64,
            ),
            where=(
                total_time_by_state[:, None]
                > 0
            ),
        )

        return (
            transition_counts,
            transition_rates,
        )
