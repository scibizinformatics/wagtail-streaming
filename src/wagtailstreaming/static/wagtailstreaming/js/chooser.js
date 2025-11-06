function createStreamChooser(id) {
  const chooserElement = document.querySelector(`#${id}-chooser`);
  const streamTitle = chooserElement.querySelector('[data-chooser-title]');
  const input = document.getElementById(id);

  const getAction = (selectA, selectB) =>
    chooserElement.querySelector(selectA) || chooserElement.querySelector(selectB);

  const chooseAction = getAction('.action-choose', '[data-chooser-action-choose]');
  const clearAction = getAction('.action-clear', '[data-chooser-action-clear]');
  const editAction = getAction('.edit-link', '[data-chooser-edit-link]');

  chooseAction.addEventListener('click', () => {
    ModalWorkflow({
      url: chooserElement.dataset.chooserUrl,
      onload: STREAM_CHOOSER_MODAL_ONLOAD_HANDLERS,
      responses: {
        streamChosen(streamData) {
          input.value = streamData.id;
          streamTitle.textContent = streamData.title;
          chooserElement.classList.remove('blank');
          editAction.href = streamData.edit_url;
          editAction.classList.remove('w-hidden');
          state = streamData;
        }
      }
    });
  });

  clearAction?.addEventListener('click', () => {
    input.value = '';
    chooserElement.classList.add('blank');
  });

  let state = null;

  return {
    getState() { return state; },
    getValue() { return state?.id; },
    setState(streamData) {
      if (!streamData) return;
      input.value = streamData.id;
      streamTitle.textContent = streamData.title;
      editAction.href = streamData.edit_url;
      editAction.classList.remove('w-hidden');
      chooserElement.classList.remove('blank');
      state = streamData;
    },
    getTextLabel(opts) {
      const text = streamTitle.textContent || '';
      const maxLength = opts?.maxLength;
      return (maxLength && text.length > maxLength)
        ? text.substring(0, maxLength - 1) + '…'
        : text;
    },
    focus() {
      chooseAction.focus();
    }
  };
}