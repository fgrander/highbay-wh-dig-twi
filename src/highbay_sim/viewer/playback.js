// The simulated clock. Time always stays within the run, and stops at its end.

export const SPEEDS = [1, 10, 60, 600, 3600];
const INITIAL_SPEED = 60;

export function createPlayback({ duration_s, clock = () => performance.now() }) {
  let time = 0;
  let playing = false;
  let speed = INITIAL_SPEED;
  let lastUpdate = clock();

  const moveTo = (target) => {
    time = Math.min(Math.max(target, 0), duration_s);
  };

  return {
    get time_s() {
      return time;
    },
    get playing() {
      return playing;
    },
    get speed() {
      return speed;
    },
    get duration_s() {
      return duration_s;
    },
    update() {
      const now = clock();
      if (playing) {
        moveTo(time + ((now - lastUpdate) / 1000) * speed);
        if (time >= duration_s) {
          playing = false;
        }
      }
      lastUpdate = now;
    },
    play() {
      if (time >= duration_s) {
        time = 0;
      }
      lastUpdate = clock();
      playing = true;
    },
    pause() {
      playing = false;
    },
    restart() {
      time = 0;
      playing = false;
    },
    moveTo,
    setSpeed(value) {
      if (!SPEEDS.includes(value)) {
        throw new RangeError(`Unsupported speed: ${value}`);
      }
      speed = value;
    },
  };
}
