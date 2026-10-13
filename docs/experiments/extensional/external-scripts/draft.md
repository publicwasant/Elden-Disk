# 1.7.2 - Extension External-Script

## 1b - the foundation (May be, can be redesign later..)

__(Inspired by Arduino (Setup & Loop) Script)__

### Interface

**Sudo-code:**

```python
import time
import threading
from abc import ABC, abstractmethod

class Interface(ABC):
    """
    Interface Class สำหรับกำหนดโครงสร้างรูปแบบ External Scripts
    และจัดการระบบ Multi-threading แยกอิสระต่อ 1 สคริปต์
    """
    def __init__(self, name="ArduinoTask"):
        self.name = name
        self.is_running = True
        self._thread = None

    @abstractmethod
    def setup(self):
        """ทำงานครั้งเดียวก่อนเริ่มลูป (บังคับให้คลาสลูกต้องมี)"""
        pass

    @abstractmethod
    def loop(self):
        """ทำงานวนซ้ำไปเรื่อยๆ (บังคับให้คลาสลูกต้องมี)"""
        pass

    def run(self):
        """กระบวนการภายใน Thread ทำการเรียก setup และวน loop"""
        self.setup()
        try:
            while self.is_running:
                self.loop()
        except Exception as e:
            print(f"[{self.name}] Error occurred: {e}")
        finally:
            print(f"--- [{self.name}] Stopped ---")

    def start(self):
        """คำสั่งสำหรับสร้างและเริ่ม Thread ของสคริปต์นี้"""
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self):
        """คำสั่งส่งสัญญาณหยุดการทำงาน และรอให้ Thread ปิดตัวลง"""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
```

### User Script

**Sudo-code:**

```python
import time

class ScriptA(Interface):
    def __init__(self):
        super().__init__(name="LED_Task")
        self.led_state = False

    def setup(self):
        print(f"[{self.name}] Setup: กำหนดค่าพอร์ต GPIO สำหรับ LED สำเร็จ")

    def loop(self):
        self.led_state = not self.led_state
        state_str = "HIGH (ON)" if self.led_state else "LOW (OFF)"
        print(f"[{self.name}] สถานะ LED -> {state_str}")
        time.sleep(1.0)


class ScriptB(Interface):
    def __init__(self):
        super().__init__(name="Sensor_Task")
        self.temperature = 25.0

    def setup(self):
        print(f"[{self.name}] Setup: เชื่อมต่อเซ็นเซอร์ I2C สำเร็จ")

    def loop(self):
        # จำลองค่าอุณหภูมิขยับขึ้นลงเล็กน้อย
        self.temperature += 0.5
        print(f"[{self.name}] อุณหภูมิที่อ่านได้: {self.temperature:.1f} °C")
        time.sleep(2.5)
```

### Use-Case

__(May be creating script injection in Feat: Extension of the tools)__

**Sudo-code**

```python
if __name__ == "__main__":
    # 1. Load All User's scripts
    scripts = ...

    # 2. สั่งเริ่มต้น (Start) ทุกๆ สคริปต์ให้ทำงานแยก Thread ของตัวเอง
    for script in scripts:
        script.start()

    try:
        # Main Thread ทำหน้าที่คอยสแตนด์บายไม่ให้โปรแกรมปิดตัวลงทันที
        while True:
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n=== ได้รับคำสั่งหยุดการทำงาน (KeyboardInterrupt) ===")
        print("กำลังปิดทุก Thread อย่างปลอดภัย...")

        # 4. สั่งหยุด (Stop) ทุกสคริปต์และรอให้ Thread เคลียร์ตัวเองเรียบร้อย
        for script in scripts:
            script.stop()

        print("=== ปิดโปรแกรมสมบูรณ์แบบ ===")
```

### Package Organization (May be, can be redesign later..)

```text
../code/eldendisk/extension
 ├─ /external_scripts
 |   ├─ /users
 |   |  ├─ <script-name-a>.py
 |   |  ├─ <script-name-b>.py
 |   |  └─ <script-name-c>.py
 |   └─ <interface>.py
 └─ /innovate-items (completed as is it)
```

__(Users ที่ว่านี่คือผมและเหล่า Dev ด้วยกันเองหนิแหล่ะ)__

### The Why

ณ ตอนนี้และในอนาคต เราวามารถมีส่วนรวมกับ tools ได้ โดยมี external script เข้ามา user สร้าง scripts; tools give everthing to user (args, read and write func, etc.); user design tools mechanism; tools inject, running on threads (1-script-per-tread)

extension มี status บอก ตัวไหนรันผ่าน run -> live; ตัวไหน error ก็ kill -> dead;

ตัวอย่างการสร้าง script โดยที่ตอบโจทย์ปัญหาที่เราเจอตอนนี้คือ Innovate-Items Reverse Cursed Technique Spell ตอนนี้เมื่อเรา Build regulation.in -> swap by vault -> scan & write text/color จบ เล่นได้สนุก มีข้อควม effect เฉพาะ

แต่ปัญหามันอยู่ที่ว่าตัว effect's color ที่เรา write rgb ลงไป มันดันไป impact ตัว item อื่นๆ ที่ตัว Reverse Cursed Technique ดัดแปลงมา

และตามข้อมูลที่เราได้ระหว่างการพัฒนา ซึ่งนำมาต่อยอดต่อได้ว่า:
1. เก็บ address ไว้ เช่นใน session ของ vault ผูกกับ pid และเวลาที่เกมเริ่ม เพื่อไม่ให้ใช้ข้ามรอบ
2. ตรวจ bytes ที่ address นั้นก่อนเขียน แล้ว scan ใหม่เมื่อไม่ตรง
3. สำหรับสี ต้องจำว่าเราทาสีอะไรไว้ จะได้ทาทับด้วยสีใหม่ได้ ตอนนี้ copy ที่ทาแล้วจะถูกทาซ้ำด้วยสีอื่นไม่ได้ในเกมเดียวกัน ข้อนี้คือสิ่งที่จะได้ประโยชน์มากที่สุดครับ เพราะจะลองสีได้ทันทีโดยไม่ต้องปิดเกม

ใช่ครับ address ที่ได้ใช้ได้แน่นอนในเกมรอบนั้น ฝั่ง text เขียนซ้ำได้สบาย ฝั่ง color ถ้าเกมเอาไปใช้ทีหลังก็ปล่อยให้เกมไป แค่ตรวจไม่กี่ byte ก่อนเขียนก็จะรู้ทันที แล้วค่อย scan ใหม่

ีexternal-script จะทำอะไร? 
1. user สร้าง script 
2. tools give (args, read and write func, etc.) as `import ... from edstdlib (edstdlib means elden disk standard library)`
3. user เขียน condition ใน function loop() ว่า `read --query character.effect*` เจอ id ของ Reverse Cursed Technique ให้ `write ..color..` specific  id โดยผ่านการ scan ตอนเข้าโลกมาแล้ว เพราะงัน write ได้สบายไม่ส่งผลอะไรมากอยู่แล้ว เหมือน feat: write ทั่วไปของ tools และให้ redo หลังจาก buff_durations หมด กลับไปเป็น สีเดิม 

ปิดจ๊อบ