import copy


class Orders(object):  # 指令
    def __init__(self, x=0, y=0, rotate=0,
                 shoot=0, yaw=0, auto_aim=True, auto_shoot=True,
                 do_route_plan=False, dir_relate_to_map=False, swing=False):
        self.x = x  # 启动路径规划时
        self.y = y
        self.rotate = rotate  # -1~1	底盘，-1：左转，0：不动，1：右转	a/d
        self.shoot = shoot  # 0~1	是否射击，0：否，1：是	space
        self.yaw = yaw  # -1~1	云台，-1：左转，0：不动，1：右转	b/m
        self.auto_aim = auto_aim  # 0~2	是否启用自瞄，0：否，1：自瞄模式，2：自动瞄准射击模式
        self.auto_shoot = auto_shoot  # 0~2	是否启用自瞄，0：否，1：自瞄模式，2：自动瞄准射击模式
        self.do_route_plan = do_route_plan
        self.freq_update_goal = 20
        self.dir_relate_to_map = dir_relate_to_map
        self.swing = swing
        self.shoot_target_enemy = -1

class Orders_set(object):
    def __init__(self, num):
        self.set = []
        for n in range(num):
            self.set.append(Orders())
        self.sets_new = copy.deepcopy(self.set)

    def reset(self):
        self.set = copy.deepcopy(self.sets_new)

    def combine(self, orders0, orders1):
        self.set = orders0.set + orders1.set



class My_Agent(object):
    def __init__(self, _id, options):
        self.id = _id
        self.robot_blue_num = options.robot_b_num
        self.robot_red_num = options.robot_r_num
        self.num_robots = options.robot_b_num if _id else options.robot_r_num
        self.robot_ids = [(i + self.robot_red_num if _id else i) for i in range(self.num_robots)]
        self.orders = Orders_set(self.num_robots)
        self.keyboard_orders = [{'forward': 'K_w', 'backward': 'K_s', 'left': 'K_q', 'right': 'K_e',
                                 'left_rotate': 'K_a', 'right_rotate': 'K_d',
                                 'yaw_left': 'K_z', 'yaw_right': 'K_c', 'shoot': 'K_SPACE', 'aim': 'K_LSHIFT'},
                                {'forward': 'K_p', 'backward': 'K_SEMICOLON', 'left': 'K_o', 'right': 'K_LEFTBRACKET',
                                 'left_rotate': 'K_l', 'right_rotate': 'K_QUOTE',
                                 'yaw_left': 'K_PERIOD', 'yaw_right': 'K_SLASH', 'shoot': 'K_RSHIFT', 'aim': 'K_1'},
                                {'forward': 'K_u', 'backward': 'K_j', 'left': 'K_y', 'right': 'K_i',
                                 'left_rotate': 'K_h', 'right_rotate': 'K_k',
                                 'yaw_left': 'K_n', 'yaw_right': 'K_COMMA', 'shoot': 'K_v', 'aim': 'K_1'},
                                {'forward': 'K_KP8', 'backward': 'K_KP5', 'left': 'K_KP7', 'right': 'K_KP9',
                                 'left_rotate': 'K_KP4', 'right_rotate': 'K_KP6',
                                 'yaw_left': 'K_KP1', 'yaw_right': 'K_KP3', 'shoot': 'K_DOWN', 'aim': 'K_1'}]
        self.no_order_state = True
        self.keyboard_orders = self.keyboard_orders[2: self.num_robots + 2] if _id else \
            self.keyboard_orders[0:self.num_robots]  # 蓝色和红色各自专用按键
        self.action_type = options.action_type
        if self.action_type == 'Hybrid':
            self.actions = {'Continuous': {'x': [-2, 2], 'y': [-2, 2], 'rotate': [-2, 2]},
                            'Discrete': {'shoot': 2}}
        elif self.action_type == 'MultiDiscrete' or 'Discrete':
            self.actions = {'x': 3, 'y': 3, 'rotate': 3, 'shoot': 2}

        self.state = {'x': [0, 808],
                      'y': [0, 448],
                      'angle': [-180, 180],
                      'bullet': [0, 500]
                      }

    def decode_actions(self, game_state, actions=None):  # 根据动作编码，解码产生动作；键盘操控不需要解码
        self.orders.reset()
        event = game_state.KB_events
        for i, key_board_order in enumerate(self.keyboard_orders):
            for key in self.keyboard_orders[i].keys():
                if key_board_order[key] in event:
                    if key == 'forward':
                        self.orders.set[i].x += 1
                    if key == 'backward':
                        self.orders.set[i].x -= 1
                    if key == 'left':
                        self.orders.set[i].y -= 1
                    if key == 'right':
                        self.orders.set[i].y += 1
                    if key == 'left_rotate':
                        self.orders.set[i].rotate -= 1
                    if key == 'right_rotate':
                        self.orders.set[i].rotate += 1
                    if key == 'yaw_left':
                        self.orders.set[i].yaw -= 1
                    if key == 'yaw_right':
                        self.orders.set[i].yaw += 1
                    if key == 'shoot':
                        self.orders.set[i].shoot += 1
                    if key == 'aim':
                        self.orders.set[i].shoot_target_enemy += 1
        return self.orders