/*
 Copyright (c) 2015, GEM Foundation.

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU Affero General Public License as
 published by the Free Software Foundation, either version 3 of the
 License, or (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU Affero General Public License for more details.

 You should have received a copy of the GNU Affero General Public License
 along with this program.  If not, see <https://www.gnu.org/licenses/agpl.html>.
 */

(function($, Backbone, _) {
    var calculation_table;

    var progressHandlingFunction = function(progress) {
        var percent = progress.loaded / progress.total * 100;
        $('.bar').css('width', percent + '%');
        if (percent == 100) {
            dialog.hide();
        }
    };

    var dialog = (function ()
                  {
                      var pleaseWaitDiv = $('<div class="modal hide" id="pleaseWaitDialog" data-backdrop="static" data-keyboard="false"><div class="modal-header"><h1>Processing...</h1></div><div class="modal-body"><div class="progress progress-striped active"><div class="bar" style="width: 0%;"></div></div></div></div>');
                      return {
                          show: function(msg, progress) {
                          $('h1', pleaseWaitDiv).text(msg);
                          if (progress) {
                          progressHandlingFunction({loaded: 0, total: 1});
                          } else {
                          progressHandlingFunction({loaded: 1, total: 1});
                      }
                              pleaseWaitDiv.modal();
                          },
                          hide: function () {
                              pleaseWaitDiv.modal('hide');
                          }
                      };
                  })();

    var diaerror = (function ()
                  {
                      var errorDiv = $('<div id="errorDialog" class="modal fade" style="display: none;" data-keyboard="true" tabindex="-1">\
                <div class="modal-dialog">\
                  <div class="modal-content">\
                    <div class="modal-header">\
                      <h4 class="modal-title">Calculation not accepted: traceback</h4>\
                    </div>\
                    <div class="modal-body" style="font-size: 12px;"><pre style="font-size: 12px;" class="modal-body-pre"></pre>\
                    </div>\
                    <div class="modal-footer">\
                      <span id="diaerror_scroll_enabled_box" style="display: none;"><input type="checkbox" id="diaerror_scroll_enabled" checked>\
                      Auto Scroll</span>&nbsp;&nbsp;&nbsp;\
                      <button type="button" class="btn btn-default" data-dismiss="modal">Close</button>\
                    </div>\
                  </div>\
                </div>\
</div>');
                      errorDiv.bind('hide', function() { calculation_table.hide_log(); });
                      return {
                          getdiv: function() {
                              return errorDiv;
                          },

                          show: function(title, msg) {
                              if (title != null) {
                                  $('.modal-title', errorDiv).html(title);
                              }
                              if (msg != null) {
                                  $('.modal-body-pre', errorDiv).html(msg);
                              }
                              errorDiv.modal();
                          },

                          append: function(title, msg) {
                              if (title != null) {
                                  $('.modal-title', errorDiv).html(title);
                              }
                              $( msg ).appendTo( $('.modal-body-pre', errorDiv) );
                          },

                          scroll_to_bottom: function(ctx) {
                              ctx.scrollTop(ctx[0].scrollHeight);
                          },

                          hide: function () {
                              errorDiv.modal('hide');
                          }
                      };
                  })();

    var CalculationTable = Backbone.View.extend(
        {
            /* the html element where the table is rendered */
            el: $('#my-calculations'),

            logXhr: null,
            logId: -1,
            logIsNew: false,
            logLinesAll: 0,
            logLines: 0,
            logTimeout: null,

            initialize: function(options) {

                /* whatever happens to any calculation, re-render the table */
                _.bindAll(this, 'render');
                this.calculations = options.calculations;
                this.calculations.bind('reset', this.render);
                this.calculations.bind('add', this.render);
                this.calculations.bind('remove', this.render);

                /* if false, it prevents the table to be refreshed */
                this.can_be_rendered = true;

                this.render();
            },

            events: {
                "click .btn-danger": "remove_calculation",
                "click .btn-traceback": "show_traceback",
                "click .btn-log": "show_log",
                "click .btn-file": "on_run_risk_clicked",
                "change .btn-file input": "on_run_risk_queued"
            },

            /* When an input dialog is opened, it is very important to not re-render the table */
            on_run_risk_clicked: function(e) {
                /* if a file input dialog has been opened do not refresh the calc table */
                this.can_be_rendered = false;
            },

            on_run_risk_queued: function(e) {
                this.can_be_rendered = true;
            },

            remove_calculation: function(e) {
                e.preventDefault();
                var calc_id = $(e.target).attr('data-calc-id');
                var view = this;
                diaerror.show("Removing calculation " + calc_id, "...");
                $.post(gem_oq_server_url + "/v1/calc/" + calc_id + "/remove"
                     ).success(
                         function(data, textStatus, jqXHR)
                         {
                             diaerror.show("Removing calculation " + calc_id, "Calculation " + calc_id + " removed.");
                             view.calculations.remove([view.calculations.get(calc_id)]);
                         }
                     ).error(
                         function(jqXHR, textStatus, errorThrown)
                         {
                             if (jqXHR.status == 404) {
                                 diaerror.show("Removing calculation " + calc_id, "Failed: calculation " + calc_id + " not found.");
                             }
                             else {
                                 diaerror.show("Removing calculation " + calc_id, "Failed: " + textStatus);
                             }
                         }
                     );
            },

            show_traceback: function(e) {
                var calc_id = $(e.target).attr('data-calc-id');

                var myXhr = $.ajax({url: gem_oq_server_url + "/v1/calc/" + calc_id + "/traceback",
                                    error: function (jqXHR, textStatus, errorThrown) {
                                        if (jqXHR.status == 404) {
                                            diaerror.show("Calculation " + calc_id + " not found.");
                                        }
                                        else {
                                            diaerror.show("Error retrieving traceback for calculation " + calc_id, textStatus);
                                        }
                                        // alert("Error: " + textStatus);
                                    },
                                    success: function (data, textStatus, jqXHR) {
                                        if (data.length == 0) {
                                            diaerror.show("Traceback not found for calculation " + calc_id, []);
                                        }
                                        else {
                                            var out = "";
                                            var ct = 0;
                                            for (s in data) {
                                                if (data[s] == "")
                                                    continue;
                                                out += '<p ' + (ct % 2 == 1 ? 'style="background-color: #ffffff;"' : '') + '>' + data[s] + '</p>';
                                                ct++;
                                            }
                                            diaerror.show("Traceback of calculation " + calc_id, out);
                                        }
                                        // alert("Success: " + textStatus);
                                    }});
            },

            _show_log_priv: function(is_new, calc_id, is_running, from) {
                var was_running = is_running;

                // TO CHECK hide_log method enable console.log and take a look
                // console.log("_show_log_priv: begin");
                if (this.logXhr != null) {
                    this.logXhr.abort();
                    this.logXhr = null;
                }
                if (is_new) {
                    if (this.logTimeout != null) {
                        window.clearTimeout(this.logTimeout);
                        this.logTimeout = null;
                    }
                }
                var obj = this;

                this.logXhr = $.ajax({url: gem_oq_server_url + "/v1/calc/" + calc_id + "/log/" + from + ":",
                                      error: function (jqXHR, textStatus, errorThrown) {
                                          if (jqXHR.status == 404) {
                                              diaerror.show("Log of calculation " + calc_id + " not found.");
                                          }
                                          else {
                                              diaerror.show("Error retrieving log for calculation " + calc_id, textStatus);
                                          }
                                          obj.logIsNew = false;
                                      },
                                      success: function (data, textStatus, jqXHR) {
                                          var delay = 250;

                                          if (is_new) {
                                              obj.logLines = 0;
                                              obj.logLinesAll = 0;
                                          }
                                          else {
                                              // if data is empty check if job is still running
                                              if (is_running) {
                                                  if (data.length == 0) {
                                                      var ajax, status;

                                                      delay = 1000;

                                                      ajax = $.ajax({url: gem_oq_server_url + "/v1/calc/" + calc_id + "/status",
                                                                     async: false}).done(function (data) { status = data.is_running; });
                                                      if (status !== true) {
                                                          is_running = false;
                                                      }
                                                  }
                                              }
                                          }
                                          var out = "";

                                          for (s in data) {
                                              if (data[s] == "") {
                                                  obj.logLinesAll++;
                                                  continue;
                                              }
                                              out += '<p ' + (obj.logLines % 2 == 1 ? 'style="background-color: #ffffff;"' : '') + '>' + data[s] + '</p>';
                                              obj.logLines++;
                                              obj.logLinesAll++;
                                          }

                                          var title;
                                          if (is_running) {
                                              var dt;
                                              dt = new Date();
                                              title = "Log of calculation " + calc_id + " - " + dt.toString();
                                          }
                                          else if (was_running != is_running) {
                                              title = "Log of calculation " + calc_id + " - finished";
                                          }
                                          else {
                                              title = "Log of calculation " + calc_id;
                                          }

                                          if (obj.logIsNew) {
                                              diaerror.show(title, out);
                                          }
                                          else {
                                              diaerror.append(title, out);
                                          }
                                          if ($("#diaerror_scroll_enabled").prop( "checked" )) {
                                              diaerror.scroll_to_bottom($('.modal-body', diaerror.getdiv()));
                                          }

                                          if (is_running) {
                                              function log_update(obj)
                                              {
                                                  obj._show_log_priv(false, obj.logId, true, obj.logLinesAll);
                                              }

                                              obj.logTimeout = window.setTimeout(log_update, delay, obj);
                                          }
                                          else {
                                              $('#diaerror_scroll_enabled_box').hide();
                                          }

                                          obj.logIsNew = false;
                                      }});
            },

            show_log: function(e) {
                var calc_id = $(e.target).attr('data-calc-id');
                var is_running = ($(e.target).attr('is-running') == "true");

                this.logId = calc_id;
                this.logIsNew = true;

                this._show_log_priv(true, calc_id, is_running, "0");
                $('#diaerror_scroll_enabled_box').show();
            },

            hide_log: function(e) {
                if (this.logTimeout != null) {
                    window.clearTimeout(this.logTimeout);
                    this.logTimeout = null;
                }
                if (this.logXhr != null) {
                    this.logXhr.abort();
                    this.logXhr = null;
                }
                $('#diaerror_scroll_enabled_box').hide();
            },

            render: function() {
                if (!this.can_be_rendered) {
                    return;
                };
                this.$el.html(_.template($('#calculation-table-template').html(),
                                         { calculations: this.calculations.models }));
            }
        });

    var Calculation = Backbone.Model.extend({
        defaults: {
            map: null,
            layers: []
        }
    });

    var Calculations = Backbone.Collection.extend(
        {
            model: Calculation,
            url: gem_oq_server_url + "/v1/calc/list?relevant=true"
        });
    var calculations = new Calculations();

    var refresh_calcs;

    function setTimer() {
        refresh_calcs = setInterval(function() { calculations.fetch({reset: true}) }, 3000);
    }


    /* classic event management */
    $(document).ready(
        function() {
            calculation_table = new CalculationTable({ calculations: calculations });
            calculations.fetch({reset: true});
            setTimer();

            /* XXX. Reset the input file value to ensure the change event
               will be always triggered */
            $(document).on("click", 'input[name=archive]',
                           function(e) { this.value = null; });
            $(document).on("change", 'input[name=archive]',
                           function(e) {
                               dialog.show('Uploading calculation', true);
                               var input = $(e.target);
                               var form = input.parents('form')[0];

                               $(form).ajaxSubmit(
                                   {
                                    xhr: function() {  // custom xhr to add progress bar management
                                        var myXhr = $.ajaxSettings.xhr();
                                        if(myXhr.upload){ // if upload property exists
                                            myXhr.upload.addEventListener('progress', progressHandlingFunction, false);
                                        }
                                        return myXhr;
                                    },
                                    success: function(data) {
                                        calculations.add(new Calculation(data), {at: 0});
                                    },
                                    error: function(xhr) {
                                        dialog.hide();
                                        var s, out, data = $.parseJSON(xhr.responseText);
                                        var out = "";
                                        var ct = 0;
                                        for (s in data) {
                                            if (data[s] == "")
                                                continue;
                                            out += '<p ' + (ct % 2 == 1 ? 'style="background-color: #ffffff;"' : '') + '>' + data[s] + '</p>';
                                            ct++;
                                        }
                                        diaerror.show("Calculation not accepted: traceback", out);
                                    }});
                           });

            $(document).on('hidden.bs.modal', 'div[id^=traceback-]',
                           function(e) {
                               setTimer();
                           });

        });
})($, Backbone, _, gem_oq_server_url);