class WMTabs {
  constructor(node) {
    this.tabContainer = node;
    this.tabButtons = this.tabContainer.querySelectorAll('[role="tab"]');
    this.tabList = this.tabContainer.querySelector('[role="tablist"]');
    this.tabPanels = this.tabContainer.querySelectorAll('[role="tabpanel"]');
    this.tabTriggerLinks = this.tabContainer.querySelectorAll('[data-tab-trigger]');
    this.keydownEventListener = this.keydownEventListener.bind(this);
    this.animate = this.tabContainer.hasAttribute('data-tabs-animate');
    this.disableURL = this.tabContainer.hasAttribute('data-tabs-disable-url');

    this.state = {
      activeTabID: '',
      transition: 150,
      initialPageLoad: true,
      css: {
        animate: 'animate-in',
      },
      keys: {
        end: 'End',
        home: 'Home',
        left: 'ArrowLeft',
        up: 'ArrowUp',
        right: 'ArrowRight',
        down: 'ArrowDown',
      },
      direction: {
        ArrowLeft: -1,
        ArrowRight: 1,
      },
    };

    this.onComponentLoaded();
  }

  onComponentLoaded() {
    this.bindEvents();
    if (this.tabButtons) {
      this.setAriaControlsByHref(this.tabButtons);
      const tabActive = [...this.tabButtons].find(
        (button) => button.getAttribute('aria-selected') === 'true',
      );

      if (window.location.hash && !this.disableURL) {
        this.selectTabByURLHash();
      } else if (tabActive) {
        this.tabPanels.forEach((tab) => {
          tab.hidden = true;
        });
        this.selectTab(tabActive);
      } else {
        this.selectFirstTab();
      }
    }

    if (this.tabTriggerLinks) {
      this.setAriaControlsByHref(this.tabTriggerLinks);
    }
  }

  unSelectActiveTab(newTabId) {
    if (newTabId === this.state.activeTabID || !this.state.activeTabID) {
      return;
    }

    const tabContent = this.tabContainer.querySelector(
      `#${this.state.activeTabID}`,
    );

    if (!tabContent) {
      return;
    }

    if (this.animate) {
      this.animateOut(tabContent);
    } else {
      tabContent.hidden = true;
    }

    const tab = this.tabContainer.querySelector(
      `a[href='#${this.state.activeTabID}']`,
    );

    tab.setAttribute('aria-selected', 'false');
    tab.setAttribute('tabindex', '-1');
  }

  selectTab(tab) {
    if (!tab) {
      return;
    }

    const tabContentId = tab.getAttribute('aria-controls');
    if (tabContentId) {
      this.unSelectActiveTab(tabContentId);
    }

    this.state.activeTabID = tabContentId;
    const linkedTab = this.tabContainer.querySelector(
      `a[href="${tab.getAttribute('href')}"][role="tab"]`,
    );

    if (linkedTab) {
      linkedTab.setAttribute('aria-selected', 'true');
      linkedTab.removeAttribute('tabindex');
    }

    tab.setAttribute('aria-selected', 'true');
    tab.removeAttribute('tabindex');

    const tabContent = this.tabContainer.querySelector(`#${tabContentId}`);
    if (!tabContent) {
      return;
    }

    if (this.animate) {
      this.animateIn(tabContent);
    } else {
      tabContent.hidden = false;
    }

    if (this.state.initialPageLoad) {
      setTimeout(() => {
        window.scrollTo(0, 0);
      }, this.state.transition * 2);
    }

    this.tabList.dispatchEvent(
      new CustomEvent('switch', {
        detail: { tab: tab.getAttribute('href').replace('#', '') },
      }),
    );
    document.dispatchEvent(new CustomEvent('wagtail:tab-changed'));

    if (!this.disableURL) {
      this.setURLHash(tabContentId);
    }
  }

  animateIn(tabContent) {
    setTimeout(() => {
      tabContent.hidden = false;
      setTimeout(() => {
        tabContent.classList.add(this.state.css.animate);
      }, this.state.transition);
    }, this.state.transition);
  }

  animateOut(tabContent) {
    tabContent.classList.remove(this.state.css.animate);
    setTimeout(() => {
      tabContent.hidden = true;
    }, this.state.transition);
  }

  bindEvents() {
    if (this.tabButtons) {
      this.tabButtons.forEach((tab, index) => {
        tab.addEventListener('click', (e) => {
          e.preventDefault();
          this.selectTab(tab);
        });
        tab.addEventListener('keydown', this.keydownEventListener);
        tab.index = index;
      });

      window.addEventListener('popstate', (e) => {
        if (e.state && e.state.tabContent) {
          const tab = this.getTabElementByHref(`#${e.state.tabContent}`);
          if (tab) {
            this.selectTab(tab);
            tab.focus();
          }
        }
      });
    }

    if (this.tabTriggerLinks) {
      this.tabTriggerLinks.forEach((trigger) => {
        trigger.addEventListener('click', (e) => {
          e.preventDefault();
          const tab = this.getTabElementByHref(trigger.getAttribute('href'));
          if (tab) {
            this.selectTab(tab);
            tab.focus();
          }
        });
      });
    }
  }

  getTabElementByHref(href) {
    return this.tabContainer.querySelector(`a[href="${href}"][role="tab"]`);
  }

  keydownEventListener(event) {
    const keyPressed = event.key;
    const { keys } = this.state;

    switch (keyPressed) {
      case keys.left:
      case keys.right:
        this.switchTabOnArrowPress(event);
        break;
      case keys.end:
        event.preventDefault();
        this.focusLastTab();
        break;
      case keys.home:
        event.preventDefault();
        this.focusFirstTab();
        break;
      default:
        break;
    }
  }

  selectTabByURLHash() {
    if (window.location.hash) {
      const cleanedHash = window.location.hash.replace(/[^\w\-#]/g, '');
      const tab = this.getTabElementByHref(cleanedHash);
      if (tab) {
        this.selectTab(tab);
      } else {
        this.selectFirstTab();
      }
    }
  }

  setURLHash(tabId) {
    if (
      !this.state.initialPageLoad &&
      (!window.history.state || window.history.state.tabContent !== tabId)
    ) {
      window.history.pushState({ tabContent: tabId }, null, `#${tabId}`);
    }
    this.state.initialPageLoad = false;
  }

  switchTabOnArrowPress(event) {
    const pressed = event.key;
    const { direction } = this.state;
    const { keys } = this.state;
    const tabs = this.tabButtons;

    if (direction[pressed]) {
      const target = event.target;
      if (target.index !== undefined) {
        if (tabs[target.index + direction[pressed]]) {
          const tab = tabs[target.index + direction[pressed]];
          tab.focus();
          this.selectTab(tab);
        } else if (pressed === keys.left) {
          this.focusLastTab();
        } else if (pressed === keys.right) {
          this.focusFirstTab();
        }
      }
    }
  }

  focusFirstTab() {
    const tab = this.tabButtons[0];
    tab.focus();
    this.selectTab(tab);
  }

  focusLastTab() {
    const tab = this.tabButtons[this.tabButtons.length - 1];
    tab.focus();
    this.selectTab(tab);
  }

  selectFirstTab() {
    this.selectTab(this.tabButtons[0]);
    this.state.activeTabID = this.tabButtons[0].getAttribute('aria-controls');
  }

  setAriaControlsByHref(links) {
    links.forEach((link) => {
      link.setAttribute(
        'aria-controls',
        link.getAttribute('href').replace('#', ''),
      );
    });
  }
}

const initWMTabs = (tabs = document.querySelectorAll('[data-wm-tabs]')) => {
  tabs.forEach((tabSet) => new WMTabs(tabSet));
};
