import rclpy, sys
import rclpy.logging as logging
import matplotlib.pyplot as plt

import sim_data_collection.analysis.analysis as analysis
import sim_data_collection.utils as utils
from sim_data_collection.analysis.dataset import Dataset

def has_empty_table(): pass

def main():
    assert len(sys.argv) > 1, "Please provide a database path."
    rclpy.init()
    db_paths = sys.argv[1:]
    dataset = Dataset()
    success = True
    try:
        logger = logging.get_logger("integrity_check")
        logger.info(f"Integrity check starting. Checking {len(db_paths)} databases.")

        progress = 0.0
        for i, db_path in enumerate(db_paths):
            new_progress = 100.0 * ((i + 1) / len(db_paths))
            if new_progress - progress >= 1:
                logger.info(f"PROGRESS: {new_progress}%")
                progress = new_progress
            dataset.open(db_path)
            for msg_id in analysis.msg_ids:
                msgs = dataset.get_msgs(msg_id).fetchall()
                msgs.sort(key=lambda x: x[1])
                if len(msgs) == 0:
                    logger.error(f"{db_path}:{msg_id} EMPTY TABLE!")
                    success = False
                    continue
            dataset.close()
    except Exception as e:
        logger.error(f"An error has occured: {e}")
        success = False
    finally:
        if success == True:
            logger.info("Integrity check succeeded.")
            rclpy.shutdown()
            sys.exit(0)
        else:
            logger.info("Integrity check failed. Reason: empty tables")
            rclpy.shutdown()
            sys.exit(1)

if __name__ == "__main__":
    main()