# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.


from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill
import time

import socket
socket.setdefaulttimeout(300)
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from pyvirtualdisplay import Display

import logging


# disable logs from easyprocess, or there is too much spam from display init
logging.getLogger("easyprocess").setLevel(logging.WARNING)

# disable selenium logger
from selenium.webdriver.remote.remote_connection import LOGGER as selenium_log
selenium_log.setLevel(logging.WARNING)

__author__ = 'jarbas'


class BrowserService(MycroftSkill):
    def __init__(self):
        super(BrowserService, self).__init__(name="BrowserSkill")
        # start virtual display
        self.display = Display(visible=0, size=(800, 600))
        self.display.start()
        self.driver = None
        self.elements = {}
        self.timeout = 300

    def initialize(self):
        i = 0
        started = self.start_browser()
        while not started and i < 5:
            self.timeout += 60
            i += 1
            started = self.start_browser()

        if not started:
            raise EnvironmentError("could not start selenium webdriver")

        self.log.info("browser service started: " + str(started))
        self.emitter.on("browser_restart_request", self.handle_restart_browser)
        self.emitter.on("browser_close_request", self.handle_close_browser)
        self.emitter.on("browser_url_request", self.handle_go_to_url)
        self.emitter.on("browser_title_request", self.handle_title_request)
        self.emitter.on("browser_go_back_request", self.handle_go_back)
        self.emitter.on("browser_current_url_request", self.handle_current_url)
        self.emitter.on("browser_get_element", self.handle_get_element)
        self.emitter.on("browser_get_elements", self.handle_get_elements)
        self.emitter.on("browser_get_element_text", self.handle_get_element_text)
        self.emitter.on("browser_available_elements_request", self.handle_available_elements)
        self.emitter.on("browser_send_keys_to_element", self.handle_send_keys)
        self.emitter.on("browser_reset_elements", self.handle_reset_elements)
        self.emitter.on("browser_click_element", self.handle_click_element)
        self.emitter.on("browser_clear_element", self.handle_clear_element)
        self.emitter.on("browser_get_cookies_request", self.handle_get_cookies)
        self.emitter.on("browser_add_cookies_request", self.handle_add_cookies)
        self.emitter.on("browser_get_atr_request", self.handle_get_attribute)

    def handle_get_attribute(self, message):
        atr = message.data.get("atr")
        elem = message.data.get("element_name")
        if elem not in self.elements.keys():
            self.log.error("No such element")
            self.emitter.emit(Message("browser_get_atr_response", {"atr": atr, "result":None, "error":"No such element"}))
            return
        result = self.elements[elem].get_attribute(atr)
        self.emitter.emit(Message("browser_get_atr_response", {"atr": atr, "result":result}))

    def handle_get_cookies(self, message):
        cookies = self.driver.get_cookies()
        self.emitter.emit(Message("browser_get_cookies_response", {"cookies":cookies}))

    def handle_title_request(self, message):
        self.emitter.emit(Message("browser_title_response", {"title": self.driver.title}))

    def handle_add_cookies(self, message):
        cookies = message.data.get("cookies", [])
        if len(cookies) == 0:
            self.emitter.emit(Message("browser_add_cookies_response",
                                      {"success": False, "cookies":
                                          cookies, "cookie_number": len(cookies)}))
            return
        for cookie in cookies:
            self.driver.add_cookie(cookie)
        self.emitter.emit(Message("browser_add_cookies_response",
                                  {"success":True, "cookies":cookies, "cookie_number":len(cookies)}))

    def handle_go_back(self, message):
        self.driver.back()
        self.emitter.emit(Message("browser_go_back_result", {"success":
                                                                 True, "url": self.driver.current_url}))

    def handle_current_url(self, message):
        self.emitter.emit(Message("browser_current_url_result", {"success":
                                                                     True, "url": self.driver.current_url, "title":self.driver.title}))

    def start_browser(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception as e:
                self.log.debug("tried to close driver but: " + str(e))

        try:
            self.driver = webdriver.Firefox(timeout=self.timeout)
            return True
        except Exception as e:
            self.log.error("Exception: " + str(e))
        return False

    def handle_clear_element(self, message):
        # TODO error checking, see if element in self.elemtns.keys()
        name = message.data.get("element_name")
        try:
            self.elements[name].clear()
            self.emitter.emit(Message("browser_element_cleared",
                                      {"success": True, "element": name}))
        except Exception as e:
            self.log.error(e)
            self.emitter.emit(Message("browser_element_cleared",
                                      {"success": False, "element": name}))

    def handle_reset_elements(self, message):
        self.elements = {}
        self.emitter.emit(Message("browser_elements_reset_result", {"elements": self.elements}))

    def handle_available_elements(self, message):
        self.emitter.emit(Message("browser_available_elements", {"elements": self.elements}))

    def handle_send_keys(self, message):
        # TODO error checking, see if element in self.elemtns.keys()
        name = message.data.get("element_name")
        key = message.data.get("special_key")
        text = message.data.get("text")
        element = self.elements[name]
        if key:
            if text == "RETURN":
                element.send_keys(Keys.RETURN)
            else:
                # TODO all keys
                self.emitter.emit(Message("browser_sent_keys",
                                          {"success":False, "name": name, "data": text, "error": "special key not yet implemented"}))
                return
        else:
            element.send_keys(text)
            # TODO change this, needed because text may be big
            time.sleep(1)
        self.emitter.emit(Message("browser_sent_keys", {"success":True,
                                                        "name": name, "data": text}))

    def handle_get_elements(self, message):
        get_by = message.data.get("type") #xpath, css, name, id
        data = message.data.get("data") # name, xpath expression....
        name = message.data.get("element_name")# how to call this element later
        try:
            i = 0
            if get_by == "xpath":
                for e in self.driver.find_elements_by_xpath(data):
                    self.elements[name+str(i)] = e
                    i+=1
            elif get_by == "css":
                for e in self.driver.find_elements_by_css(data):
                    self.elements[name + str(i)] = e
                    i += 1
            elif get_by == "name":
                for e in self.driver.find_elements_by_name(data):
                    self.elements[name + str(i)] = e
                    i += 1
            elif get_by == "class":
                for e in self.driver.find_elements_by_class_name(data):
                    self.elements[name + str(i)] = e
                    i += 1
            elif get_by == "link_text":
                for e in self.driver.find_elements_by_link_text(data):
                    self.elements[name + str(i)] = e
                    i += 1
            elif get_by == "partial_link_text":
                for e in self.driver.find_elements_by_partial_link_text(data):
                    self.elements[name + str(i)] = e
                    i += 1
            elif get_by == "tag_name":
                for e in self.driver.find_elements_by_tag_name(data):
                    self.elements[name + str(i)] = e
                    i += 1
            elif get_by == "id":
                for e in self.driver.find_elements_by_id(data):
                    self.elements[name + str(i)] = e
                    i += 1
            else:
                self.log.error("Invalid element type: " + get_by)
                self.emitter.emit(
                    Message("browser_elements_stored", {"name": name,
                                                        "type": get_by, "data": data, "success": False}))
                return
            self.emitter.emit(Message("browser_elements_stored",
                                      {"name":name, "type":get_by, "data":data, "success":True}))
        except Exception as e:
            self.log.error(e)
            self.emitter.emit(Message("browser_elements_stored", {"name":
                                                                      name, "type": get_by, "data": data, "success":False}))

    def handle_get_element(self, message):
        get_by = message.data.get("type") #xpath, css, name, id
        data = message.data.get("data").encode('ascii', 'ignore').decode('ascii') # name, xpath expression....
        name = message.data.get("element_name")# how to call this element later
        try:
            # todo extra
            if get_by == "xpath":
                self.elements[name] = self.driver.find_element_by_xpath(data)
            elif get_by == "css":
                self.elements[name] = self.driver.find_element_by_css(data)
            elif get_by == "name":
                self.elements[name] = self.driver.find_element_by_name(data)
            elif get_by == "class":
                self.elements[name] = self.driver.find_element_by_class_name(data)
            elif get_by == "link_text":
                self.elements[name] = self.driver.find_element_by_link_text(data)
            elif get_by == "partial_link_text":
                self.elements[name] = self.driver.find_element_by_partial_link_text(data)
            elif get_by == "tag_name":
                self.elements[name] = self.driver.find_element_by_tag_name(data)
            elif get_by == "id":
                self.elements[name] = self.driver.find_element_by_id(data)
            else:
                self.log.error("Invalid element type: " + get_by)
                self.emitter.emit(
                    Message("browser_element_stored", {"name": name,
                                                       "type": get_by, "data": data, "success": False}))
                return
            self.emitter.emit(Message("browser_element_stored",
                                      {"name":name, "type":get_by, "data":data, "success":True}))
        except Exception as e:
            self.log.error(e)
            self.emitter.emit(Message("browser_element_stored", {"name":
                                                                     name, "type": get_by, "data": data, "success":False}))

    def handle_get_element_text(self, message):
        # TODO error checking, see if element in self.elemtns.keys()
        name = message.data.get("element_name")
        element = self.elements[name]
        self.emitter.emit(Message("browser_element_text", {"name": name, "text": element.text}))

    def handle_click_element(self, message):
        name = message.data.get("element_name")
        try:
            self.elements[name].click()
            self.emitter.emit(Message("browser_element_clicked",
                                      {"success":True, "element": name}))
        except Exception as e:
            self.log.error(e)
            self.emitter.emit(Message("browser_element_clicked",
                                      {"success": False, "element": name}))

    def handle_close_browser(self, message):
        try:
            self.driver.close()
        except Exception as e:
            self.log.error(e)
        self.emitter.emit(Message("browser_closed", {}))

    def handle_restart_browser(self, message):
        started = self.start_browser()
        self.emitter.emit(Message("browser_restart_result",
                                  {"success":started}))

    def handle_go_to_url(self, message):
        url = message.data.get("url")
        if "http" not in url:
            url = "http://"+url
        fails = 0
        while fails < 5:
            try:
                self.driver.get(url)
                self.log.info(u"url: " + self.driver.current_url)
                self.log.info(u"title: " + self.driver.title)
                break
            except Exception as e:
                self.log.error(e)
            time.sleep(0.5)
            fails += 1
        self.emitter.emit(Message("browser_url_opened", {"result": self.driver.current_url, "page_title": self.driver.title, "requested_url": url}))

    def stop(self):
        try:
            self.driver.quit()
            Display.close()
        except Exception as e:
            self.log.error(e)

    def shutdown(self):
        self.stop()
        self.emitter.remove("browser_restart_request",
                        self.handle_restart_browser)
        self.emitter.remove("browser_close_request", self.handle_close_browser)
        self.emitter.remove("browser_url_request", self.handle_go_to_url)
        self.emitter.remove("browser_title_request", self.handle_title_request)
        self.emitter.remove("browser_go_back_request", self.handle_go_back)
        self.emitter.remove("browser_current_url_request",
                        self.handle_current_url)
        self.emitter.remove("browser_get_element", self.handle_get_element)
        self.emitter.remove("browser_get_elements", self.handle_get_elements)
        self.emitter.remove("browser_get_element_text",
                        self.handle_get_element_text)
        self.emitter.remove("browser_available_elements_request",
                        self.handle_available_elements)
        self.emitter.remove("browser_send_keys_to_element", self.handle_send_keys)
        self.emitter.remove("browser_reset_elements", self.handle_reset_elements)
        self.emitter.remove("browser_click_element", self.handle_click_element)
        self.emitter.remove("browser_clear_element", self.handle_clear_element)
        self.emitter.remove("browser_get_cookies_request",
                        self.handle_get_cookies)
        self.emitter.remove("browser_add_cookies_request",
                        self.handle_add_cookies)
        self.emitter.remove("browser_get_atr_request", self.handle_get_attribute)
        self.display.stop()
        super(BrowserService, self).shutdown()


def create_skill():
    return BrowserService()
