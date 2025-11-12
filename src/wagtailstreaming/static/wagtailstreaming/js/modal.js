STREAM_CHOOSER_MODAL_ONLOAD_HANDLERS = {
  'chooser': function(modal, jsonData) {
    const searchUrl = $('form.video-search', modal.body).attr('action');
    const resultsContainer = $('#stream-results', modal.body);

    const collectionChooser = $('#collection_chooser_collection_id', modal.body);
    const searchInput = $('#id_q', modal.body);

    const initialPageResultsHtml = resultsContainer.html();

    let currentTag;
    let request;

    function ajaxifyLinks (context) {
      $('a.stream-choice', context).on('click', (e) => {
        e.preventDefault();
        modal.loadUrl(e.currentTarget.href);
      });

      $('.pagination a', context).on('click', (e) => {
        e.preventDefault();
        
        const query = searchInput.val().trim();
        const params = {
          p: e.currentTarget.getAttribute('data-page'),
          collection_id: collectionChooser.val() || '',
        };

        if (query.length) params.q = query;
        if (currentTag) params.tag = currentTag;

        request = fetchResults(params);
      });

      $('a[data-ordering]', context).on('click', (e) => {
        e.preventDefault();

        request = fetchResults({
          q: searchInput.val().trim(),
          collection_id: collectionChooser.val() || '',
          ordering: e.currentTarget.getAttribute('data-page')
        });
      });
    }

    function fetchResults(params) {
      if (request) request.abort();

      request = $.ajax({
        url: searchUrl,
        data: params,
        dataType: 'html', 
        method: 'GET', 

        success(html) {
          request = null;
          resultsContainer.html(html);
          ajaxifyLinks(resultsContainer);
        },

        error(xhr, status, error) {
          console.error(`Stream search failed: ${status} - ${error}`);
          request = null;
        },
      });

      return request;
    }

    function abortRequest() {
      if (request && typeof request.abort === 'function') {
        request.abort();
        request = null;
      }
    }

    function search() {
      const query = searchInput.val().trim();
      const collection_id = collectionChooser.val() || '';

      if (query || collection_id) {
        currentTag = null;
        abortRequest();

        request = fetchResults({
          q: query,
          collection_id: collection_id
        });
      }

      else {
        resultsContainer.html(initialPageResultsHtml);
        ajaxifyLinks(resultsContainer);
      }

      return false;
    }

    ajaxifyLinks(modal.body);
    initWMTabs();

    $('form.video-upload', modal.body).on('submit', async function(e) {
      e.preventDefault();

      const form = this;
      const formData = new formData(form);
      const titleInput = form.querySelector('#id_stream-chooser-upload-title');

      const title = titleInput?.value.trim() || '';
      if (!title) {
        if (!titleInput.hasAttribute('aria-invalid')) {
          titleInput.setAttribute('aria-invalid', 'true');

          const field = titleInput.closest('[data-field]');
          field?.classList.add('w-field--error');

          const errors = field?.querySelector('[data-field-errors]');
          const icon = errors?.querySelector('.icon');
          if (icon) icon.removeAttribute('hidden');

          const errorElement = document.createElement('p');
          errorElement.classList.add('error-message');
          errorElement.innerHTML = gettext('This field is required.');
          errors?.appendChild(errorElement);
        }

        setTimeout(cancelSpinner, 500);
        return;
      }

      try {
        const response = await fetch(form.action, {
          method: 'POST', 
          body: formData, 
        });

        if (!response.ok) {
          throw new Error(`${response.status} ${response.statusText}`);
        }

        const text = await response.text();
        modal.loadResponseText(text);
      } 
      
      catch (err) {
        const message = `
          ${jsonData['error_message']}<br />
          ${err.message}
        `;

        $('#upload').append(`
          <div class="help-block help-critical">
            <strong>${jsonData['error_label']}: </strong>${message}
          </div>
        `);
      }
    });

    $('form.video-search', modal.body).on('submit', search);

    searchInput.on('input', function() {
      abortRequest();
      clearTimeout($(this).data('timer'));
      const wait = setTimeout(search, 200);
      $(this).data('timer', wait);
    });

    collectionChooser.on('change', search);

    $('a.suggested-tag').on('click', (e) => {
      e.preventDefault();

      currentTag = e.currentTarget.textContent.trim();
      searchInput.val('');
      request = fetchResults({
        'tag': currentTag,
        collection_id: collectionChooser.val()
      });
    });


    modal.body.querySelectorAll('[name="stream-chooser-upload-file"]')
    .forEach((fileInput) => {
      fileInput.addEventListener('change', () => {
        const form = fileInput.closest('form');
        const titleInput = form.querySelector('#id_stream-chooser-upload-title');

        if (titleInput && titleInput.value.trim() === '') {
          const filePath = fileInput.value;
          const filename = filePath.split('\\').pop().replace(/\.[^.]+$/, '');
          titleInput.value = filename;
        }
      });
    });

    $('[name="stream-chooser-upload-tags"]', modal.body)
    .each(function() {
      $(this).tagit({
        autocomplete: { source: jsonData['tag_autocomplete_url'] }
      });
    });
  },

  'video_chosen': function(modal, jsonData) {
    modal.respond('streamChosen', jsonData['result']);
    modal.close();
  },

  'select_format': function(modal) {
    $('form', modal.body).on('submit', function() {
      var formdata = new FormData(this);

      $.post(this.action, $(this).serialize(), modal.loadResponseText, 'text');

      return false;
    });
  }
};
