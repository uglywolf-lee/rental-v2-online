/*
 * date8.js - 공용 날짜 입력 모듈
 * 모든 날짜 입력을 "숫자 8자리(YYYYMMDD)" 방식으로 통일한다.
 * - 사용자는 20260723 처럼 숫자 8개만 입력한다.
 * - 스크립트가 el.value 를 읽으면 'YYYY-MM-DD'(ISO) 로 반환된다.
 * - 스크립트가 el.value = '2026-07-23' 로 세팅하면 화면엔 '20260723' 으로 표시된다.
 *   => 기존 제출/기본값 코드는 수정 없이 그대로 동작한다.
 * 대상: input[type=date] 또는 class="date8" 인 input
 */
(function () {
  var nativeDesc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');

  function onlyDigits(s) { return (s == null ? '' : String(s)).replace(/\D/g, '').slice(0, 8); }

  function digitsToIso(d) {
    d = onlyDigits(d);
    if (d.length !== 8) return '';
    var y = +d.slice(0, 4), m = +d.slice(4, 6), day = +d.slice(6, 8);
    if (m < 1 || m > 12 || day < 1 || day > 31) return '';
    return d.slice(0, 4) + '-' + d.slice(4, 6) + '-' + d.slice(6, 8);
  }

  function isoToDigits(s) { return onlyDigits(s); } // 대시 제거: '2026-07-23'->'20260723'

  window.date8 = { digitsToIso: digitsToIso, isoToDigits: isoToDigits };

  function upgrade(el) {
    if (!el || el.__date8) return;
    el.__date8 = true;

    try { el.type = 'text'; } catch (e) {}
    el.setAttribute('inputmode', 'numeric');
    el.setAttribute('maxlength', '8');
    el.setAttribute('pattern', '\\d{8}');
    el.classList.add('date8');
    if (!el.getAttribute('data-keep-placeholder')) {
      el.placeholder = 'YYYYMMDD (예: 20260723)';
    }
    // 기존에 들어있던 값(대시 포함 가능)을 8자리로 변환해 표시
    nativeDesc.set.call(el, isoToDigits(nativeDesc.get.call(el)));

    // 입력 시 숫자만, 최대 8자리 유지
    el.addEventListener('input', function () {
      var d = onlyDigits(nativeDesc.get.call(el));
      if (d !== nativeDesc.get.call(el)) nativeDesc.set.call(el, d);
    });

    // value 프로퍼티 재정의: 스크립트는 ISO 로 읽고 쓰되 화면은 8자리로 유지
    Object.defineProperty(el, 'value', {
      configurable: true,
      get: function () { return digitsToIso(nativeDesc.get.call(el)); },
      set: function (v) { nativeDesc.set.call(el, isoToDigits(v)); }
    });
  }

  function initDate8(root) {
    root = root || document;
    var list = root.querySelectorAll('input.date8, input[type=date]');
    Array.prototype.forEach.call(list, upgrade);
  }
  window.initDate8 = initDate8;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initDate8(); });
  } else {
    initDate8();
  }
})();
