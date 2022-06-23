import numpy as np
import torch
import numpy.random as rd


class ReplayBuffer:
    def __init__(self, max_len, state_dim, action_dim, if_discrete, if_multi_discrete):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.max_len = max_len
        self.now_len = 0
        self.next_idx = 0
        self.if_full = False
        if if_discrete:
            self.action_dim = 1
        elif if_multi_discrete:
            self.action_dim = action_dim.size
            action_dim = sum(action_dim)
        else:
            self.action_dim = action_dim  # for self.sample_all(
        self.tuple = None
        self.np_torch = torch

        other_dim = 1 + 1 + self.action_dim + action_dim
        # other = (reward, mask, action, a_noise) for continuous action
        # other = (reward, mask, a_int, a_prob) for discrete action
        self.buf_other = np.empty((max_len, other_dim), dtype=np.float32)
        self.buf_state = np.empty((max_len, state_dim), dtype=np.float32)

    def append_buffer(self, state, other):  # CPU array to CPU array
        self.buf_state[self.next_idx] = state
        self.buf_other[self.next_idx] = other

        self.next_idx += 1
        if self.next_idx >= self.max_len:
            self.if_full = True
            self.next_idx = 0

    def extend_buffer(self, state, other):  # CPU array to CPU array
        size = len(other)
        next_idx = self.next_idx + size
        if next_idx > self.max_len:
            self.buf_state[self.next_idx:self.max_len] = state[:self.max_len - self.next_idx]
            self.buf_other[self.next_idx:self.max_len] = other[:self.max_len - self.next_idx]
            self.if_full = True

            next_idx = next_idx - self.max_len
            self.buf_state[0:next_idx] = state[-next_idx:]
            self.buf_other[0:next_idx] = other[-next_idx:]
        else:
            self.buf_state[self.next_idx:next_idx] = state
            self.buf_other[self.next_idx:next_idx] = other
        self.next_idx = next_idx

    def extend_buffer_from_list(self, trajectory_list):
        state_ary = np.array([item[0] for item in trajectory_list], dtype=np.float32)
        other_ary = np.array([item[1] for item in trajectory_list], dtype=np.float32)
        self.extend_buffer(state_ary, other_ary)
        return state_ary.shape[0]

    def sample_batch(self, batch_size):
        indices = rd.randint(self.now_len - 1, size=batch_size)
        r_m_a = self.buf_other[indices]
        return (r_m_a[:, 0:1],  # reward
                r_m_a[:, 1:2],  # mask = 0.0 if done else gamma
                r_m_a[:, 2:],  # action
                self.buf_state[indices],  # state
                self.buf_state[indices + 1])  # next_state

    def sample_all(self):
        all_other = torch.as_tensor(self.buf_other[:self.now_len], device=self.device)
        return (all_other[:, 0],  # reward
                all_other[:, 1],  # mask = 0.0 if done else gamma
                all_other[:, 2:2 + self.action_dim],  # action
                all_other[:, 2 + self.action_dim:],  # action_noise or action_prob
                torch.as_tensor(self.buf_state[:self.now_len], device=self.device))  # state

    def update_now_len(self):
        self.now_len = self.max_len if self.if_full else self.next_idx

    def empty_buffer(self):
        self.next_idx = 0
        self.now_len = 0
        self.if_full = False


class MultiAgentMultiEnvsReplayBuffer(ReplayBuffer):
    def __init__(self, max_len, state_dim, action_dim, if_discrete, if_multi_discrete, env):
        super().__init__(max_len, state_dim, action_dim, if_discrete, if_multi_discrete)
        if env is None:
            raise NotImplementedError
        self.env_num = env.env_num
        self.total_trainers_envs = env.get_trainer_ids()
        self.buf_other = [[[] for _ in trainers]
                          for trainers in self.total_trainers_envs]
        self.buf_state = [[[] for _ in trainers]
                          for trainers in self.total_trainers_envs]

    def extend_buffer_from_list(self, trajectory_list):
        step_num = 0
        states_ary = [[] for _ in range(self.env_num)]
        others_ary = [[] for _ in range(self.env_num)]
        for env_id in range(self.env_num):
            for n in self.total_trainers_envs[env_id]:
                state_ary = np.array([item[0] for item in trajectory_list[env_id][n]], dtype=np.float32)
                step_num += state_ary.shape[0]
                states_ary[env_id].append(state_ary)
                others_ary[env_id].append(np.array([item[1] for item in trajectory_list[env_id][n]], dtype=np.float32))
        self.extend_buffer(states_ary, others_ary)
        return step_num

    def extend_buffer(self, states, others):  # CPU array to CPU array
        for env_id in range(self.env_num):
            for i in range(len(self.total_trainers_envs[env_id])):
                state = states[env_id][i]
                other = others[env_id][i]
                size = len(other)
                next_idx = self.next_idx + size
                if next_idx > self.max_len:
                    self.buf_state[env_id][i][self.next_idx:self.max_len] = state[:self.max_len - self.next_idx]
                    self.buf_other[env_id][i][self.next_idx:self.max_len] = other[:self.max_len - self.next_idx]
                    self.if_full = True

                    next_idx = next_idx - self.max_len
                    self.buf_state[env_id][i][0:next_idx] = state[-next_idx:]
                    self.buf_other[env_id][i][0:next_idx] = other[-next_idx:]
                else:
                    self.buf_state[env_id][i][self.next_idx:next_idx] = state
                    self.buf_other[env_id][i][self.next_idx:next_idx] = other
                self.next_idx = next_idx

    def sample_all(self):
        reward = [[] for _ in range(self.env_num)]
        mask = [[] for _ in range(self.env_num)]
        action = [[] for _ in range(self.env_num)]
        action_noise = [[] for _ in range(self.env_num)]
        state = [[] for _ in range(self.env_num)]
        for env_id in range(self.env_num):
            for agent_id in range(len(self.total_trainers_envs[env_id])):
                buf_other = np.array(self.buf_other[env_id][agent_id])
                buf_state = np.array(self.buf_state[env_id][agent_id])
                reward[env_id].append(torch.as_tensor(buf_other[:, 0], device=self.device))
                mask[env_id].append(torch.as_tensor(buf_other[:, 1], device=self.device))
                action[env_id].append(torch.as_tensor(buf_other[:, 2:2 + self.action_dim], device=self.device))
                action_noise[env_id].append(torch.as_tensor(buf_other[:, 2 + self.action_dim:], device=self.device))
                state[env_id].append(torch.as_tensor(buf_state, device=self.device))
        return reward, mask, action, action_noise, state
