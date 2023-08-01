from rclpy.node import Node as ROSNode
from eufs_msgs.msg import ConeArrayWithCovariance, CarState, ConeWithCovariance
from ugrdv_msgs.msg import Cone3dArray, Cone3d
from scipy.spatial.transform import Rotation
from typing import List, Tuple
import math
import numpy as np

class Node(ROSNode):
    def __init__(self):
        super().__init__("simulated_perception_node")
        # set up publishers and subscriptions
        self.subs = {
            "ground_truth_cones" : self.create_subscription(
                ConeArrayWithCovariance,
                "/ground_truth/track",
                self.on_gt_cones,
                1
            ),
            "ground_truth_state" : self.create_subscription(
                CarState,
                "/ground_truth/state",
                self.on_gt_car_state,
                1
            ),
        } 
        self.pubs = {
            "simulated_perception" : self.create_publisher(
                ConeArrayWithCovariance,
                "/ugrdv/perception/epsrc_cones",
                1
            )
        }
        update_hz = 10
        self.timer = self.create_timer(
            1 / update_hz,
            self.timer_callback
        )
        self.last_car_state = {
            "x" : 0.0,
            "y" : 0.0,
            "yaw" : 0.0
        }
        self.last_gt_cones = Cone3dArray()
    
    def on_gt_cones(self, msg):
        self.get_logger().info("Got %d blue cones." % (len(msg.blue_cones)))
        self.last_gt_cones = self.convert_eufs_cones(msg)

    def on_gt_car_state(self, msg):
        self.get_logger().info("Car: (%d, %d, %d)" % (msg.pose.pose.position.x, msg.pose.pose.position.y, self.get_car_heading(msg)))
        x, y = msg.pose.pose.position.x, msg.pose.pose.position.y
        yaw = self.get_car_heading(msg)
        self.last_car_state["x"] = x
        self.last_car_state["y"] = y
        self.last_car_state["yaw"] = yaw

    def get_car_heading(self, car_state):
        quat = Rotation.from_quat((
            car_state.pose.pose.orientation.x,
            car_state.pose.pose.orientation.y,
            car_state.pose.pose.orientation.z,
            car_state.pose.pose.orientation.w,
        ))
        euler = quat.as_euler("XYZ")
        yaw = euler[2]
        return yaw

    def convert_eufs_cones(self, msg):
        def do_array(arr, colour):
            new_arr = []
            for eufs in arr:
                ugr = Cone3d()
                ugr.position.x = eufs.point.x
                ugr.position.y = eufs.point.y
                ugr.colour = colour
                new_arr.append(ugr)
            return new_arr

        result = Cone3dArray()
        result.header = msg.header
        result.cones = \
            do_array(msg.blue_cones, Cone3d.BLUE) + \
            do_array(msg.yellow_cones, Cone3d.YELLOW) + \
            do_array(msg.orange_cones, Cone3d.ORANGE) + \
            do_array(msg.big_orange_cones, Cone3d.LARGEORANGE) + \
            do_array(msg.unknown_color_cones ,Cone3d.UNKNOWN)
        return result

    def convert_ugr_cones(self, cones):
        new = ConeArrayWithCovariance()
        new.header = cones.header
        for cone in cones.cones:
            eufs = ConeWithCovariance()
            eufs.point.x = cone.position.x
            eufs.point.y = cone.position.y
            if cone.colour == Cone3d.BLUE:
                new.blue_cones.append(eufs)
            elif cone.colour == Cone3d.YELLOW:
                new.yellow_cones.append(eufs)
            elif cone.colour == Cone3d.ORANGE:
                new.orange_cones.append(eufs)
            elif cone.colour == Cone3d.LARGEORANGE:
                new.big_orange_cones.append(eufs)
            else:
                new.unknown_color_cones.append(eufs)
        return new

    def timer_callback(self):
        self.publish()

    def publish(self):
        fov = math.radians(110.0)
        distance = 12.0
        cropped_cones = self.crop_to_fov(
            self.last_gt_cones,
            self.last_car_state,
            fov,
            distance
        )
        ## TODO: add in the model
        ## TODO: parameterise the node
        cropped_cones_eufs = self.convert_ugr_cones(cropped_cones)
        self.pubs["simulated_perception"].publish(cropped_cones_eufs)

    def crop_to_fov(self, cones: List[Cone3d],
                    car_state: dict, fov: float,
                    max_distance: float) -> List[Cone3d]:
        conearray = Cone3dArray()
        result = conearray.cones
        x, y, yaw = car_state["x"], car_state["y"], car_state["yaw"]
        fmin, fmax = -fov/2, fov/2
        rot = np.array([
            [np.cos(yaw), np.sin(yaw)],
            [-np.sin(yaw), np.cos(yaw)]
        ])
        carpos = np.array([
            [x],
            [y]
        ])
        for cone in cones.cones:
            # put into local frame
            conepos = np.array([
                [cone.position.x],
                [cone.position.y]
            ])
            conepos = rot @ (conepos - carpos)
            # check angle
            theta = math.atan2(conepos[1], conepos[0])
            # check distance
            dist = np.linalg.norm(conepos, ord=1) 
            # add to result if good
            if theta >= fmin and theta <= fmax and dist <= max_distance:
                result.append(cone)

        return conearray