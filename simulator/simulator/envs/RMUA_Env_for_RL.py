"""
Env_for_RL of ICRA RMUA Environment


Author: DQ, HITSZ
Date: June 8th, 2021

这里开始与强化学习接轨
关于动作解码的部分在rl_trainer.py中
"""
import sys
import gym
import numpy as np
import copy
from simulator.envs import kernel_game
from simulator.envs.options import Parameters

sys.path.append('./simulator/simulator/envs/')
sys.path.append('./simulator/envs/')


class RMUA_Multi_agent_Env(gym.Env):
    metadata = {'render.modes': ['human', 'rgb_array'],
                'video.frames_per_second': 200}
    env_name = 'Robomaster'
    target_return = 50

    def __init__(self, args=Parameters()):
        self.do_render = args.render
        self.args = args
        self.simulator = kernel_game.Simulator(args)
        self.max_step = args.episode_step if args.episode_step else \
            args.episode_time * args.frame_num_one_second // args.frame_num_one_step

        self.init_obs_space()
        self.init_action_space(args.action_type)

        # reward
        self.reward_range = (float("inf"), float("-inf"))
        self.reward_text = None
        if self.do_render:
            self.reward_text = {}
        self.trainer_ids = []
        self.nn_enemy_ids = []
        for agent in self.simulator.agents:
            if agent.name == 'rl_trainer':
                self.trainer_ids += agent.robot_ids
            if agent.name == 'nn_enemy':
                self.nn_enemy_ids += agent.robot_ids
        self.rewards = [{} for _ in self.trainer_ids]
        self.rewards_episode = [{} for _ in self.trainer_ids]
        self.rewards_record = [[] for _ in self.trainer_ids]

        self.r_win_record = {'win':0.0, 'fail':0.0, 'draw':0.0}
        self.r_win_rate = 0.0
        # env
        self.delta_dist_matrix = [[0 for _ in range(self.simulator.state.robot_num)] for _ in
                                  range(self.simulator.state.robot_num)]
        # flags
        self.cal_public_obs_already = False

    def init_obs_space(self):
        self.obs_low = []
        self.obs_high = []
        self.obs_set = [{} for _ in range(self.simulator.parameters.robot_num)]
        # 縮小倍數：
        self.obs_set_scale = [[] for _ in range(self.simulator.parameters.robot_num)]

        robot_index = 0
        for agent in self.simulator.agents:
            for n in agent.robot_ids:
                for state_ in agent.state:
                    self.obs_set[robot_index]['robots[' + str(n) + '].' + state_] = agent.state[state_]
                    self.obs_low.append(agent.state[state_][0])
                    self.obs_high.append(agent.state[state_][1])
                    self.obs_set_scale[robot_index].append(agent.state[state_][1])
                robot_index += 1
        # state besides agent(最后有下划线表示不直接应用）
        if self.simulator.state.buff_mode:
            self.public_obs_set = {'time': [0, 180],
                                   'buff1_': [0, 5],
                                   'buff2_': [0, 5],
                                   'buff3_': [0, 5],
                                   'buff4_': [0, 5],
                                   'buff5_': [0, 5],
                                   'buff6_': [0, 5]
                                   }
        else:
            self.public_obs_set = {'time': [0, 180]}
        for n in range(1, self.simulator.state.robot_num):
            self.public_obs_set.update({'dist_' + str(n) + '_': [0, 924],
                                        'x_dist_' + str(n) + '_': [0, 808],
                                        'y_dist_' + str(n) + '_': [0, 448],
                                        'relative_angle_' + str(n) + '_': [-180, 180]
                                        })

        for state_ in self.public_obs_set:
            self.obs_low.append(self.public_obs_set[state_][0])
            self.obs_high.append(self.public_obs_set[state_][1])

        # self.obs_buff = [(buff[0] if buff[1] else 0) for buff in self.simulator.state.buff]
        self.observation_space = gym.spaces.Box(np.array(self.obs_low), np.array(self.obs_high))

    def init_action_space(self, action_type):
        # 合计各个agent的动作空间总和
        if action_type == 'Discrete':
            actions = 1
        else:
            actions = []
        agent = None
        for agent_ in self.simulator.agents:
            if agent_.name == 'rl_trainer':
                agent = agent_
        if not agent:
            print("No rl trainer")
            return
        if action_type == 'MultiDiscrete':
            for action in agent.actions:
                actions.append(agent.actions[action])
        elif action_type == 'Discrete':
            for action in agent.actions:
                actions *= agent.actions[action]
        elif action_type == 'Hybrid':
            actions = [[], [[], []]]
            for action in agent.actions['Discrete']:
                for robot in range(agent.num_robots):
                    actions[0].append(agent.actions['Discrete'][action])
            for action in agent.actions['Continuous'].keys():
                actions[1][0].append(agent.actions['Continuous'][action][0])
                actions[1][1].append(agent.actions['Continuous'][action][1])
        if action_type == 'MultiDiscrete':
            # 动作解码在rl_trainer.py中
            self.action_space = gym.spaces.MultiDiscrete(actions)
        elif action_type == 'Discrete':
            # 动作解码在rl_trainer.py中
            self.action_space = gym.spaces.Discrete(np.prod(actions))
        elif action_type == 'Hybrid':
            self.action_space = [gym.spaces.Box(np.array(actions[1][0]), np.array(actions[1][1])),
                                 gym.spaces.MultiDiscrete(actions[0])]

    def reset(self):
        if self.do_render and self.reward_text is None:
            self.reward_text = {}
        self.rewards = [{} for _ in self.trainer_ids]
        self.rewards_episode = [{} for _ in self.trainer_ids]
        self.last_dist_matrix = None
        self.simulator.reset()
        for robot in self.simulator.state.robots:
            for key in robot.robot_info_text:
                if '总分' in key:
                    robot.robot_info_text[key] = 0
        for i, n in enumerate(self.trainer_ids):
            robot = self.simulator.state.robots[n]
            robot.robot_info_plot['reward'] = self.rewards_record[i]
        return self.get_observations()

    def decode_actions(self, actions):
        if self.args.action_type == 'Discrete':
            i = 0
            actions_ = []
            for agent in self.simulator.agents:
                if agent.actions:
                    for robot in range(agent.num_robots):
                        actions_.append([])
                        action_before_decode = actions[i]
                        i += 1
                        for action_dim in agent.actions:
                            actions_[-1].append(action_before_decode % agent.actions[action_dim])
                            action_before_decode = action_before_decode // agent.actions[action_dim]
            return actions_
        else:
            actions_blank = [[None for _ in range(self.args.robot_r_num)], [None for _ in range(self.args.robot_b_num)]]
            j = 0
            for i in range(self.args.robot_r_num):
                if j < len(actions):
                    actions_blank[0][i] = np.array(actions[j])
                    j += 1
            for i in range(self.args.robot_b_num):
                if j < len(actions):
                    actions_blank[1][i] = np.array(actions[j])
                    j += 1
            return actions_blank

    def step(self, actions):
        done = self.simulator.step(self.decode_actions(actions))  # 只给其中一个传动作
        red_win = True
        blue_win = True
        for n in range(self.simulator.parameters.robot_r_num):
            if self.simulator.state.robots[n].hp > 0:
                blue_win = False
        for n in range(self.simulator.parameters.robot_b_num):
            if self.simulator.state.robots[n + self.simulator.parameters.robot_r_num].hp > 0:
                red_win = False
        done = done or red_win or blue_win
        if red_win:
            self.r_win_record['win'] += 0.001
        elif blue_win:
            self.r_win_record['blue'] += 0.001
        else:
            self.r_win_record['draw'] += 0.001
        self.r_win_rate = self.r_win_record['win']/\
                          (self.r_win_record['win']+self.r_win_record['fail']+self.r_win_record['draw'])
        r = self.compute_reward()
        # 记录每个机器人每回合的奖励：
        if done and self.do_render:
            for i in range(len(self.trainer_ids)):
                self.rewards_record[i].append(sum(self.rewards_episode[i].values()))
                if len(self.rewards_record[i]) > 500:  # 如果超过500条记录就均匀减半
                    self.rewards_record[i] = self.rewards_record[i][::2]

        return self.get_observations(), r, done, None

    def compute_reward(self):
        for i, n in enumerate(self.trainer_ids):
            robot = self.simulator.state.robots[n]
            # '''血量减少'''
            # reward -= 0.05 * robot.hp_loss.one_step
            # '''拿到补给'''
            # reward += 0.05 * robot.buff_hp.one_step
            # reward += 0.05 * robot.buff_bullet.one_step
            '''消耗子弹'''
            # self.rewards[n]['bullet_out'] = -0.005 * robot.bullet_out_record.one_step
            '''hit_enemy'''
            self.rewards[i]['hit'] = 0
            self.rewards[i]['hit'] += 2 * robot.enemy_hit_record.left.one_step
            self.rewards[i]['hit'] += 2 * robot.enemy_hit_record.right.one_step
            self.rewards[i]['hit'] += 5 * robot.enemy_hit_record.behind.one_step
            self.rewards[i]['hit'] += 1 * robot.enemy_hit_record.front.one_step
            # '''被敌军击中'''
            self.rewards[i]['hit_by_enemy'] = 0
            self.rewards[i]['hit_by_enemy'] -= 2 * robot.armor_hit_enemy_record.left.one_step
            self.rewards[i]['hit_by_enemy'] -= 2 * robot.armor_hit_enemy_record.right.one_step
            self.rewards[i]['hit_by_enemy'] -= 5 * robot.armor_hit_enemy_record.behind.one_step
            self.rewards[i]['hit_by_enemy'] -= 1 * robot.armor_hit_enemy_record.front.one_step
            # '''击中友军'''
            # reward -= 0.005 * robot.teammate_hit_record.left.one_step
            # reward -= 0.005 * robot.teammate_hit_record.right.one_step
            # reward -= 0.01 * robot.teammate_hit_record.behind.one_step
            # reward -= 0.002 * robot.teammate_hit_record.front.one_step
            # '''轮子撞墙、撞机器人'''
            # reward -= 0.001 * robot.wheel_hit_obstacle_record.one_step
            # reward -= 0.001 * robot.wheel_hit_wall_record.one_step
            # reward -= 0.001 * robot.wheel_hit_robot_record.one_step
            # '''装甲板撞墙'''
            # reward -= 0.005 * robot.armor_hit_wall_record.left.one_step
            # reward -= 0.005 * robot.armor_hit_wall_record.right.one_step
            # reward -= 0.01 * robot.armor_hit_wall_record.behind.one_step
            # reward -= 0.002 * robot.armor_hit_wall_record.front.one_step
            # reward -= 0.005 * robot.armor_hit_obstacle_record.left.one_step
            # reward -= 0.005 * robot.armor_hit_obstacle_record.right.one_step
            # reward -= 0.01 * robot.armor_hit_obstacle_record.behind.one_step
            # reward -= 0.002 * robot.armor_hit_obstacle_record.front.one_step
            # '''装甲板撞机器人'''
            # reward -= 0.005 * robot.armor_hit_robot_record.left.one_step
            # reward -= 0.005 * robot.armor_hit_robot_record.right.one_step
            # reward -= 0.01 * robot.armor_hit_robot_record.behind.one_step
            # reward -= 0.002 * robot.armor_hit_robot_record.front.one_step
            '''过热惩罚'''
            # reward -= 0.005 * robot.hp_loss_from_heat.one_step
            '''no_move惩罚'''
            # self.rewards[n]['no_move'] = -1 if robot.vx == 0 and robot.vy == 0 else 0
            '''击杀对方奖励'''
            enemy_all_defeated = True
            for i, enemy_id in enumerate(robot.enemy):
                if self.simulator.state.robots[enemy_id].hp > 0:
                    enemy_all_defeated = False
            if enemy_all_defeated:
                self.rewards[i]['K.O.'] = 300
            else:
                self.rewards[i]['K.O.'] = 0
                # '''引导：进攻模式'''
                # '''离敌人越近负奖励越小'''
                # dist = self.simulator.state.dist_matrix[n][enemy_id]
                # delta_dist = self.delta_dist_matrix[n][enemy_id]
                # self.rewards[n]['chase'] = -delta_dist * 0.1 if dist > 250 else delta_dist * 0.1

            reward = 0
            for key in self.rewards[i]:
                reward += self.rewards[i][key]
                robot.robot_info_text[key + '得分'] = self.rewards[i][key]
                if key + '总分' in robot.robot_info_text:
                    robot.robot_info_text[key + '总分'] += self.rewards[i][key]
                else:
                    robot.robot_info_text[key + '总分'] = self.rewards[i][key]
                if key in self.rewards_episode[i]:
                    self.rewards_episode[i][key] += self.rewards[i][key]
                else:
                    self.rewards_episode[i][key] = self.rewards[i][key]
            robot.robot_info_text['得分'] = reward
            if '总分' in robot.robot_info_text:
                robot.robot_info_text['总分'] += reward
            else:
                robot.robot_info_text['总分'] = reward
        return sum([sum(individual_reward.values()) for individual_reward in self.rewards])

    def calculate_public_observation(self):
        game_state = self.simulator.state
        if self.last_dist_matrix:
            for n, robot in enumerate(game_state.robots):
                for i, other_robot in enumerate(game_state.robots):
                    if n != i:
                        self.delta_dist_matrix[n][i] = self.simulator.state.dist_matrix[n][i] - \
                                                       self.last_dist_matrix[n][i]  # 代表与敌人距离的增加
        self.last_dist_matrix = copy.deepcopy(self.simulator.state.dist_matrix)

        self.public_observation = []
        for i, state in enumerate(self.public_obs_set):
            if state[-1] != '_':
                self.public_observation.append(eval('game_state.' + state) / self.public_obs_set[state][1])

        # 针对buff单独读取观测值

        if self.simulator.state.buff_mode:
            for buff_area in game_state.buff:
                if buff_area[1]:
                    self.public_observation.append((buff_area[0] + 1) / 6)  # 加一是为了区分未激活编号为0的buff和已激活buff
                else:
                    self.public_observation.append(0)
        self.cal_public_obs_already = True

    def get_individual_observation(self, robot_index):
        robot = self.simulator.state.robots[robot_index]
        # 在使用該函數前須先運行get_public_observation函數
        assert self.cal_public_obs_already, 'Please run get_public_observation function first'

        observation = []

        # 友方信息放前面，敵方信息放後面
        # 自己的信息
        for i, state in enumerate(self.obs_set[robot_index]):
            observation.append(eval('self.simulator.state.' + state) / self.obs_set_scale[robot_index][i])
            robot.robot_info_text[state] = observation[i]
        # 友方信息
        if robot.friend is not None:
            for i, state in enumerate(self.obs_set[robot.friend]):
                observation.append(eval('self.simulator.state.' + state) / self.obs_set_scale[robot.friend][i])
        # 敵方信息
        for enemy_id in robot.enemy:
            for i, state in enumerate(self.obs_set[enemy_id]):
                observation.append(eval('self.simulator.state.' + state) / self.obs_set_scale[enemy_id][i])
        # 额外部分
        observation += self.public_observation
        # 相對距离
        # 友方
        if robot.friend is not None:
            observation.append(self.simulator.state.dist_matrix[robot_index][robot.friend] / 853568)
            observation.append(self.simulator.state.x_dist_matrix[robot_index][robot.friend] / 808)
            observation.append(self.simulator.state.y_dist_matrix[robot_index][robot.friend] / 448)
            # 相对角度
            observation.append((self.simulator.state.relative_angle[robot_index, robot.friend]) / 180)
        # 敵方
        for i in robot.enemy:
            observation.append(self.simulator.state.dist_matrix[robot_index][i] / 853568)
            observation.append(self.simulator.state.x_dist_matrix[robot_index][i] / 808)
            observation.append(self.simulator.state.y_dist_matrix[robot_index][i] / 448)
            # 相对角度
            observation.append((self.simulator.state.relative_angle[robot_index, i]) / 180)

        return np.array(observation)

    def get_observations(self):
        self.calculate_public_observation()
        observations = []
        for i in range(self.args.robot_r_num + self.args.robot_b_num):
            if i in self.trainer_ids or i in self.nn_enemy_ids:
                observations.append(self.get_individual_observation(i))
            else:
                observations.append(None)  # for random agent
        self.cal_public_obs_already = False
        return observations

    def render(self, do_render=True):
        self.simulator.state.do_render = do_render
        self.do_render = do_render
        if not self.simulator.render_inited and do_render:
            self.simulator.init_render(self.args)


if __name__ == '__main__':
    args = Parameters()
    args.red_agents_path = 'src.agents.random_enemy'
    args.blue_agents_path = 'src.agents.human_agent'
    args.render_per_frame = 20
    args.episode_time = 180
    args.render = True
    args.训练模式 = False
    args.time_delay_frame = 0.1
    env = RMUA_Multi_agent_Env(args)
    env.simulator.state.pause = True
    env.reset()
    for e in range(args.episodes):
        _, _, done, _ = env.step([])
        if done:
            env.reset()
        if env.simulator.state.do_render is False:
            print('Simulator closed')
            break
