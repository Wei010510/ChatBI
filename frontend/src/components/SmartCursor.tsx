import { useEffect, useRef } from 'react';

interface Props {
  enabled: boolean;
}

// 可选的自定义悬浮标：圆环快速跟随，浅辉光缓慢跟随。
export default function SmartCursor({ enabled }: Props) {
  const cursorRef = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!enabled || !window.matchMedia('(pointer: fine)').matches) return;

    const cursor = cursorRef.current;
    const glow = glowRef.current;
    if (!cursor || !glow) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let frame = 0;
    let targetX = 0;
    let targetY = 0;
    let cursorX = 0;
    let cursorY = 0;
    let glowX = 0;
    let glowY = 0;
    let visible = false;

    const setVisible = (next: boolean) => {
      visible = next;
      cursor.dataset.visible = String(next);
      glow.dataset.visible = String(next);
      if (!next) cursor.dataset.pressed = 'false';
    };

    const handlePointerMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse') return;
      targetX = event.clientX;
      targetY = event.clientY;
      if (!visible) {
        cursorX = glowX = targetX;
        cursorY = glowY = targetY;
        setVisible(true);
      }
    };

    const handlePointerDown = (event: PointerEvent) => {
      if (event.pointerType === 'mouse' && visible) cursor.dataset.pressed = 'true';
    };
    const handlePointerUp = () => {
      cursor.dataset.pressed = 'false';
    };
    const hide = () => setVisible(false);

    const render = () => {
      const cursorEase = reduceMotion ? 1 : 0.36;
      const glowEase = reduceMotion ? 1 : 0.1;
      cursorX += (targetX - cursorX) * cursorEase;
      cursorY += (targetY - cursorY) * cursorEase;
      glowX += (targetX - glowX) * glowEase;
      glowY += (targetY - glowY) * glowEase;
      cursor.style.transform = `translate3d(${cursorX}px, ${cursorY}px, 0)`;
      glow.style.transform = `translate3d(${glowX}px, ${glowY}px, 0)`;
      frame = window.requestAnimationFrame(render);
    };

    document.documentElement.classList.add('smart-cursor-active');
    document.addEventListener('pointermove', handlePointerMove, { passive: true });
    document.addEventListener('pointerdown', handlePointerDown, { passive: true });
    document.addEventListener('pointerup', handlePointerUp, { passive: true });
    document.documentElement.addEventListener('mouseleave', hide);
    window.addEventListener('blur', hide);
    frame = window.requestAnimationFrame(render);

    return () => {
      window.cancelAnimationFrame(frame);
      document.documentElement.classList.remove('smart-cursor-active');
      document.removeEventListener('pointermove', handlePointerMove);
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('pointerup', handlePointerUp);
      document.documentElement.removeEventListener('mouseleave', hide);
      window.removeEventListener('blur', hide);
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <>
      <div ref={glowRef} className="smart-cursor-glow" aria-hidden="true">
        <span />
      </div>
      <div ref={cursorRef} className="smart-cursor" aria-hidden="true">
        <span className="smart-cursor-ring" />
        <span className="smart-cursor-dot" />
      </div>
    </>
  );
}
