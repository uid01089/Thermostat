from __future__ import annotations

import logging
from pathlib import Path
import time
import os
import paho.mqtt.client as pahoMqtt
from PythonLib.JsonUtil import JsonUtil
from PythonLib.Mqtt import Mqtt
from PythonLib.DateUtil import DateTimeUtilities
from PythonLib.MqttConfigContainer import MqttConfigContainer
from PythonLib.Scheduler import Scheduler
from PythonLib.Hysteresis import Hysteresis


logger = logging.getLogger('Thermostat')

DATA_PATH = Path(os.getenv('DATA_PATH', "."))

CONFIG = {
    "/TempSensor1/Temperature":
    {
        "Subject": "Gewaechshaus",
        "SwitchTopicControl": "cmnd/tasmota_17C3AD/POWER",
        "SwitchTopicStatus": "stat/tasmota_17C3AD/POWER",
        "SwitchOn": "ON",
        "SwitchOff": "OFF",
        "HysLowTemp": 2.0,
        "HysHighTemp": 3.0
    }
}


class Module:
    def __init__(self) -> None:
        self.scheduler = Scheduler()
        self.mqttClient = Mqtt("koserver.iot", "/house/agents/Thermostat", pahoMqtt.Client("Thermostat"))
        self.config = MqttConfigContainer(self.mqttClient, "/house/agents/Thermostat/config", DATA_PATH.joinpath("Thermostat.json"), CONFIG)

    def getConfig(self) -> MqttConfigContainer:
        return self.config

    def getScheduler(self) -> Scheduler:
        return self.scheduler

    def getMqttClient(self) -> Mqtt:
        return self.mqttClient

    def setup(self) -> None:
        self.scheduler.scheduleEach(self.mqttClient.loop, 500)
        self.scheduler.scheduleEach(self.config.loop, 60000)

    def loop(self) -> None:
        self.scheduler.loop()


class Thermostat:

    def __init__(self, module: Module) -> None:
        self.configContainer = module.getConfig()
        self.mqttClient = module.getMqttClient()
        self.scheduler = module.getScheduler()
        self.config = {}
        self.runtimeConfig = {}
        self.module = module

    def setup(self) -> None:

        self.configContainer.setup()
        self.configContainer.subscribeToConfigChange(self.__updateConfig)

        self.scheduler.scheduleEach(self.__keepAlive, 10000)

    def __receiveData(self, topic: str, payload: str) -> None:

        try:

            localConfig = self.config.get(topic)
            if localConfig:
                hysteresis = self.runtimeConfig[topic]
                temperature = float(payload)
                value = hysteresis.setValue(temperature)
                if value:
                    self.mqttClient.publishIndependentTopic(localConfig['SwitchTopicControl'], localConfig['SwitchOff'])
                else:
                    self.mqttClient.publishIndependentTopic(localConfig['SwitchTopicControl'], localConfig['SwitchOn'])

        except BaseException:
            logging.exception('')

    def __updateConfig(self, config: dict) -> None:
        self.config = config
        for topic in self.config:
            self.mqttClient.subscribeIndependentTopic(topic, self.__receiveData)
            self.runtimeConfig[topic] = Hysteresis(float(self.config[topic]['HysLowTemp']), float(self.config[topic]['HysHighTemp']))

    def __keepAlive(self) -> None:
        self.mqttClient.publishIndependentTopic('/house/agents/Thermostat/heartbeat', DateTimeUtilities.getCurrentDateString())
        self.mqttClient.publishIndependentTopic('/house/agents/Thermostat/subscriptions', JsonUtil.obj2Json(self.mqttClient.getSubscriptionCatalog()))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('Thermostat').setLevel(logging.DEBUG)

    module = Module()
    module.setup()

    Thermostat(module).setup()

    print("Thermostat is running!")

    while (True):
        module.loop()
        time.sleep(0.25)


if __name__ == '__main__':
    main()
