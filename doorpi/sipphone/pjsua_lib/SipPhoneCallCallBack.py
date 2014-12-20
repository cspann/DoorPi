#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
logger = logging.getLogger(__name__)
logger.debug("%s loaded", __name__)

import threading
import datetime
import time
import os
import pjsua as pj
from doorpi import DoorPi

class SipPhoneCallCallBack(pj.CallCallback):

    Lib = None

    inAction = False

    __DTMF = ''

    def __init__(self, PlayerID = None, call = None):
        logger.debug("__init__")
        self.PlayerID = PlayerID
        self.Lib = pj.Lib.instance()
        pj.CallCallback.__init__(self, call)

    def __del__(self):
        self.destroy()

    def destroy(self):
        logger.debug("destroy")

    def on_media_state(self):
        logger.debug("on_media_state (%s)",str(self.call.info().media_state))
        DoorPi().fire_event('OnCallMediaStateChange', {
            'remote_uri': self.call.info().remote_uri,
            'media_state': str(self.call.info().media_state)
        })

    def on_state(self):
        logger.debug("on_state (%s)", self.call.info().state_text)
        DoorPi().fire_event('OnCallStateChange', {
            'remote_uri': self.call.info().remote_uri,
            'state': self.call.info().state_text
        })

        if self.inAction is not False:
            logger.debug("wait for finished action '%s'", self.inAction)
            while self.inAction is not False: time.sleep(0.1)
            logger.debug("action finished '%s'", self.inAction)

        if self.call.info().state in [pj.CallState.CONFIRMED] \
        and self.call.info().media_state == pj.MediaState.ACTIVE:
            DoorPi().fire_event('OnCallStateConnect', {
                'remote_uri': self.call.info().remote_uri
            })
            # disconnect player with dialtone
            call_slot = self.call.info().conf_slot
            if DoorPi().sipphone.get_player_id() is not None:
                logger.trace('disconnect player')
                self.Lib.conf_disconnect(self.Lib.player_get_slot(DoorPi().sipphone.get_player_id()), 0)

            # connect to recorder
            rec_slot = DoorPi().sipphone.get_recorder_slot()
            record_while_dialing = DoorPi().sipphone.record_while_dialing
            recorder_filename = DoorPi().sipphone.parsed_recorder_filename
            if record_while_dialing is False and recorder_filename is not None:
                DoorPi().sipphone.stop_recorder_if_exists()
                rec_slot = DoorPi().sipphone.get_new_recorder_as_slot()
                self.Lib.conf_connect(0, rec_slot) # connect doorstation to recorder, if not exists
            if rec_slot is not None:
                self.Lib.conf_connect(call_slot, rec_slot) # connect phone to existing recorder

            # Connect the call to each side
            self.Lib.conf_connect(call_slot, 0)
            self.Lib.conf_connect(0, call_slot)
            logger.debug("conneted Media to call_slot %s",str(call_slot))
            DoorPi().sipphone.set_current_call(self.call)
            DoorPi().fire_event('AfterCallStateConnect', {
                'remote_uri': self.call.info().remote_uri
            })

        if self.call.info().state == pj.CallState.DISCONNECTED:
            DoorPi().fire_event('OnCallStateDisconnect', {
                'remote_uri': self.call.info().remote_uri
            })
            call_slot = self.call.info().conf_slot
            self.Lib.conf_disconnect(call_slot, 0)
            self.Lib.conf_disconnect(0, call_slot)
            DoorPi().sipphone.stop_recorder_if_exists()
            logger.debug("disconneted Media from call_slot %s",str(call_slot))
            DoorPi().sipphone.set_current_call(None)
            DoorPi().fire_event('AfterCallStateDisconnect', {
                'remote_uri': self.call.info().remote_uri
            })

    def is_admin_number(self, remote_uri = None):
        logger.debug("is_admin_number (%s)",remote_uri)

        if remote_uri is None:
            remote_uri = self.call.info().remote_uri

        possible_AdminNumbers = DoorPi().get_config().get_keys('AdminNumbers')
        for AdminNumber in possible_AdminNumbers:
            if remote_uri.startswith(AdminNumber):
                return True

        return False

    def on_dtmf_digit(self, digits):
        logger.debug("on_dtmf_digit (%s)",str(digits))

        if self.inAction is not False:
            logger.warning('still in action %s -> skip DTMF this time', self.inAction)
            return

        self.__DTMF += str(digits)

        possible_DTMF = DoorPi().config.get_keys('DTMF')

        for DTMF in possible_DTMF:
            if self.__DTMF.endswith(DTMF[1:-1]):
                self.inAction = DoorPi().config.get('DTMF', DTMF)
                logger.debug("on_dtmf_digit: get DTMF-request (%s) for action %s", DTMF, self.inAction)
                DoorPi().fire_event('OnDTMFAction', {
                    'remote_uri': self.call.info().remote_uri,
                    'action': self.inAction
                })
                DoorPi().fire_action(
                    action = self.inAction,
                    secure_source = DoorPi().sipphone.is_admin_number(self.call.info().remote_uri)
                )
                logger.debug('action %s finished', self.inAction)
                self.inAction = False

