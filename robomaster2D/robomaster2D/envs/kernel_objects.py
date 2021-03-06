import numpy as np
import random


class Record(object):
    type = 'record'
    current = 0
    one_step = 0
    one_episode = 0

    def __init__(self, name='Nobody', only_add_positive=False):
        self.only_add_positive = only_add_positive
        self.name = name

    def add(self, num=1):
        self.current = num
        if self.only_add_positive and num < 0:
            return
        self.one_step += num
        self.one_episode += num

    def reset_current(self):
        self.current = 0

    def reset_one_step(self):
        self.current = 0
        self.one_step = 0

    def reset_one_episode(self):
        self.current = 0
        self.one_step = 0
        self.one_episode = 0

    def print_one_step(self):
        return self.one_episode

    def return_one_episode(self):
        return self.one_episode


class Armor_Record(object):
    type = 'armor_record'

    def __init__(self, name='Nobody'):
        self.name = name
        self.left = Record('left')
        self.right = Record('right')
        self.front = Record('front')
        self.behind = Record('behind')

    def add(self, aromor_hit):
        if 'left' in aromor_hit:
            self.left.add()
        if 'right' in aromor_hit:
            self.right.add()
        if 'front' in aromor_hit:
            self.front.add()
        if 'behind' in aromor_hit:
            self.behind.add()

    def reset_current(self):
        for armmor in [self.left, self.right, self.front, self.behind]:
            armmor.reset_current()

    def reset_one_step(self):
        for armmor in [self.left, self.right, self.front, self.behind]:
            armmor.reset_one_step()

    def reset_one_episode(self):
        for armmor in [self.left, self.right, self.front, self.behind]:
            armmor.reset_one_episode()

    def return_one_episode(self):
        damage = 0
        damage += self.left.return_one_episode() * 40
        damage += self.right.return_one_episode() * 40
        damage += self.front.return_one_episode() * 20
        damage += self.behind.return_one_episode() * 60
        return damage

    def print_one_step(self):
        parts = ''
        if self.right.one_step:
            parts += 'R,'
        if self.left.one_step:
            parts += 'L,'
        if self.front.one_step:
            parts += 'F,'
        if self.behind.one_step:
            parts += 'B,'
        return parts


class Multi_Record(object):
    type = 'multi_record'

    def __init__(self, record_group=['front', 'left', 'behind', 'right'], num_group=1, name=""):
        self.name = name
        self.records = [{} for n in range(num_group)]
        for record in self.records:
            for record_ in record_group:
                record[record_] = Record(record_)

    def add(self, record_name, add_num=1, id_group=0):
        self.records[id_group][record_name].add(add_num)

    def reset_current(self):
        for record in self.records:
            for name in record:
                record[name].reset_current()

    def reset_one_step(self):
        for record in self.records:
            for name in record:
                record[name].reset_one_step()

    def reset_one_episode(self):
        for record in self.records:
            for name in record:
                record[name].reset_one_episode()

    def print_one_step(self):
        string = ''
        for i, record in enumerate(self.records):
            for name in record:
                if record[name].one_step:
                    string += str(i) + '.' + name[0:2] + ','
        return string


class Robot(object):
    armors = np.array([[-6.5, -28], [6.5, -28],  # behind
                       [-6.5, 28], [6.5, 28],  # front
                       [-18.5, -7], [-18.5, 6],  # left
                       [18.5, -7], [18.5, 6]  # right
                       ])
    outlines = np.array([[-22.5, -30], [22.5, -30],  # behind
                         [-22.5, 30], [22.5, 30],  # front
                         [-22.5, -30], [-22.5, 30],  # left
                         [22.5, -30], [22.5, 30]])  # right

    def __init__(self, robot_r_num, robot_num, owner=0, id=0, x=0, y=0, angle=0, bullet=50, vx=0, vy=0, yaw=0, hp=2000,
                 no_dying=False, frame_num_one_second=20.0):
        self.frame_num_one_second = frame_num_one_second
        robot_b_num = robot_num - robot_r_num
        self.owner = owner  # ?????????0????????????1?????????
        self.id = id
        if owner == 0:
            if robot_r_num == 1:
                friend = None
            elif robot_r_num == 2:
                if id == 0:
                    friend = 1
                else:
                    friend = 0
            self.enemy = [n for n in range(robot_r_num, robot_num)]
        else:
            if robot_b_num == 1:
                friend = None
            elif robot_b_num == 2:
                if id == robot_r_num:
                    friend = 1 + id
                else:
                    friend = id - 1
            self.enemy = [n for n in range(0, robot_r_num)]
        self.friend = friend
        self.x = x  # ?????????????????????????????????????????????????????????????????????
        self.vx = vx
        self.y = y
        self.vy = vy
        self.center = np.array([x, y])
        self.angle = angle  # ?????????????????? -180~180  ?????????????????????????????????x??????????????????y?????????????????????????????????
        self.yaw = yaw  # ???????????????????????? -90~90
        self.aimed_enemy = None  # ?????????????????????index
        self.heat = 0  # ????????????
        self.hp = hp  # ?????? 0~2000

        # ????????????
        self.local_map = None

        self.no_dying = no_dying
        self.reward_state = [0, 0]
        # self.can_shoot = 1  # ???????????????????????????????????????10Hz???
        self.bullet = bullet  # ???????????????
        self.bullet_speed = 25 * 100 / self.frame_num_one_second  # ??????????????? 25m/s * 100cm/m / 20frame/s = 125cm/frame
        # ?????????????????????????????????????????????????????????
        # self.yaw_angle = 0

        # ??????????????????
        self.speed_acceleration = 20 * 100 / self.frame_num_one_second / self.frame_num_one_second  # ????????? 20m/s^2 * 100cm/m / 20frame/s / 20frame/s = 5 cm/frame^2
        self.speed_max = 2 * 100 / self.frame_num_one_second  # ???????????? 2m/s * 100cm/m / 20frame/s = 10 cm/frame
        self.rotate_acceleration = 20 * 100 / self.frame_num_one_second / self.frame_num_one_second  # 5 deg/frame^2
        self.rotate_speed_max = 2 * 100 / self.frame_num_one_second  # 10 deg/frame
        self.drag_acceleration = 20 * 100 / self.frame_num_one_second / self.frame_num_one_second  # 5 cm/frame^2
        self.rotate_drag_acceleration = 20 * 100 / self.frame_num_one_second / self.frame_num_one_second  # 5 deg/frame^2

        # ????????????????????????
        self.yaw_acceleration = 20 * 100 / self.frame_num_one_second / self.frame_num_one_second  # 5 deg/frame^2
        self.yaw_rotate_speed_max = 4 * 100 / self.frame_num_one_second  # 20 deg/frame
        self.yaw_drag_acceleration = 20 * 100 / self.frame_num_one_second / self.frame_num_one_second  # 5 deg/frame^2
        # ????????????
        # self.motion = 6  # ????????????????????????x
        # self.rotate_motion = 4  # ??????????????????????????????
        # self.yaw_motion = 3  # ??????????????????????????????

        # self.camera_angle = 75 / 2  # ????????????????????????
        self.camera_angle = 180 / 2  # ????????????????????????
        self.move_discount = 2.6  # ?????????????????????????????????
        self.lidar_angle = 120 / 2  # ?????????????????????????????????

        # buff??????
        self.buff_hp = Record('buff??????')
        self.buff_bullet = Record('buff??????')
        self.freeze_time = [0, 0]  # ???????????????????????? ???3s  0~600 ???epoch???????????????
        self.freeze_state = [0, 0]  # 0: ????????????1??????????????????2???????????????
        self.cannot_shoot_overheating = False
        # ???????????????????????????????????????????????????????????????step??????????????????episode??????
        self.hp_loss_from_heat = Record('????????????')
        self.hp_loss = Record('?????????', only_add_positive=True)
        self.bullet_out_record = Record('????????????')
        self.wheel_hit_obstacle_record = Record('????????????')  # ?????????obstacle
        self.wheel_hit_wall_record = Record('?????????')  # ????????????
        self.wheel_hit_robot_record = Record('????????????')  # ??????????????????
        self.armor_hit_robot_record = Armor_Record()  # ?????????????????????
        self.armor_hit_wall_record = Armor_Record()  # ???????????????
        self.armor_hit_obstacle_record = Armor_Record()  # ????????????obstacle
        self.armor_hit_enemy_record = Armor_Record()  # ???????????????
        self.armor_hit_teammate_record = Armor_Record()  # ???????????????
        self.enemy_hit_record = Armor_Record()  # ????????????
        self.teammate_hit_record = Armor_Record()  # ????????????
        self.total_record = [self.hp_loss,
                             self.hp_loss_from_heat,
                             self.bullet_out_record,
                             self.wheel_hit_wall_record,
                             self.wheel_hit_obstacle_record,
                             self.wheel_hit_robot_record,
                             self.armor_hit_robot_record,
                             self.armor_hit_wall_record,
                             self.armor_hit_obstacle_record,
                             self.armor_hit_enemy_record,
                             self.armor_hit_teammate_record,
                             self.enemy_hit_record,
                             self.teammate_hit_record]
        self.non_armor_record = [self.hp_loss,
                                 self.hp_loss_from_heat,
                                 self.bullet_out_record,
                                 self.wheel_hit_wall_record,
                                 self.wheel_hit_obstacle_record,
                                 self.wheel_hit_robot_record]
        # ???????????????
        self.armor = {'front': '', 'left': '', 'right': '', 'behind': ''}
        # ??????render?????????
        self.robot_info_text = {}
        # ??????plot?????????
        self.robot_info_plot = {}

    def reset_frame(self):
        for record in self.total_record:
            record.reset_current()

    def reset_step(self):
        self.armor = {'front': '', 'left': '', 'right': '', 'behind': ''}
        for part in self.armor:
            if eval('self.armor_hit_robot_record.' + part + '.one_step'):
                self.armor[part] += '??????'
            if eval('self.armor_hit_wall_record.' + part + '.one_step'):
                self.armor[part] += '??????'
            if eval('self.armor_hit_obstacle_record.' + part + '.one_step'):
                self.armor[part] += '??????'
            if eval('self.armor_hit_enemy_record.' + part + '.one_step'):
                self.armor[part] += '?????????'
        for record in self.total_record:
            record.reset_one_step()

    def reset_episode(self):
        for record in self.total_record:
            record.reset_one_episode()
        self.buff_hp.reset_one_episode()
        self.buff_bullet.reset_one_episode()

    def update_hp(self):
        self.hp -= self.hp_loss.current
        if self.hp <= 0:
            if self.no_dying[self.owner]:
                self.hp = 1
            else:
                self.hp = 0
        if self.hp > 2000:
            self.hp = 2000

    def get_damage_to_enmey(self):
        return self.enemy_hit_record.return_one_episode()


class Bullet(object):
    def __init__(self, center, angle, speed=12.5, owner=0):
        self.bullet_speed = speed  # p/frame???????????????????????????pixel
        self.center = center.copy()  # ???????????????
        self.center_original = center.copy()  # ?????????????????????
        # self.speed = speed
        self.angle = angle  # ????????????????????????????????????
        self.owner = owner
        self.journey = 0
        self.journey_max = 300
        self.disappear_check_interval = 1
        self.step = 0

    def disappear(self):
        if not self.step % self.disappear_check_interval:
            self.journey = ((self.center[0] - self.center_original[0]) ** 2 + (
                    self.center[1] - self.center_original[1]) ** 2) ** 0.5
        self.step += 1
        if self.journey > self.journey_max:
            return True if random.random() > 1 / np.exp(800 / self.journey_max) else False
        return False
