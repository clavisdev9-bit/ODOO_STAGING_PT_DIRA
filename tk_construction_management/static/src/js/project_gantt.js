/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, useState, onMounted, onWillStart, onWillUnmount } = owl;
import { rpc } from "@web/core/network/rpc";
import { loadJS } from "@web/core/assets";

class PropertyProject extends Component {
    setup() {
        this.rpc = rpc;
        this.action = useService("action");
        this.orm = useService('orm')
        this.state = useState({
            currentScale: 'year',
            currentDateRangeText: '',
            startDate: null,
            endDate: null,
            showJobOrderPopup: false,
            selectedJobOrder: null
        });
        onWillStart(async () => {
            await loadJS("/tk_construction_management/static/src/js/lib/moment.min.js");
            this.state.currentDate = moment()
            this.updateDateRange();
            this.fetchData();
        })
        onWillUnmount(() => {
            this.cleanupGantt();
        });
    }

    cleanupGantt() {
        try {
            if (typeof gantt !== 'undefined') {
                gantt.clearAll();
                gantt.resetLayout();
                // Reset gantt config to default values
                gantt.config = Object.assign({}, gantt.config);
                // Clear any custom templates
                gantt.templates = Object.assign({}, gantt.templates);
            }
        } catch (error) {
            console.warn("Error during gantt cleanup:", error);
        }
    }

    /**
     * Computes and sets startDate, endDate, and display text based on current scale
     */
    async updateDateRange() {
        const { currentDate, currentScale } = this.state;
        let start, end;
        switch (currentScale) {
            case 'day':
                start = moment(currentDate).startOf('day');
                end = moment(currentDate).endOf('day');
                break;
            case 'week':
                start = moment(currentDate).startOf('week');
                end = moment(currentDate).endOf('week');
                break;
            case 'month':
                start = moment(currentDate).startOf('month');
                end = moment(currentDate).endOf('month');
                break;
            case 'year':
                start = moment(currentDate).startOf('year');
                end = moment(currentDate).endOf('year');
                break;
        }

        this.state.startDate = start.format('YYYY-MM-DD');
        this.state.endDate = end.format('YYYY-MM-DD');
        this.state.currentDateRangeText = this.getDisplayText(start, end);
    }

    getDisplayText(start, end) {
        const scale = this.state.currentScale;
        switch (scale) {
            case 'day':
                return start.format('MMMM D, YYYY');
            case 'week':
                return start.format('MMM D') + ' - ' + end.format('MMM D, YYYY');
            case 'month':
                return start.format('MMMM YYYY');
            case 'year':
                return start.format('YYYY');
            default:
                return '';
        }
    }

    async onTodayClick() {
        this.state.currentDate = moment();
        this.updateDateRange();
        this.fetchData();
    }

    async navigateTimeline(direction) {
        const { currentScale } = this.state;
        const step = (direction === 'next') ? 1 : -1;
        switch (currentScale) {
            case 'day':
                this.state.currentDate = moment(this.state.currentDate).add(step, 'days');
                break;
            case 'week':
                this.state.currentDate = moment(this.state.currentDate).add(step, 'weeks');
                break;
            case 'month':
                this.state.currentDate = moment(this.state.currentDate).add(step, 'months');
                break;
            case 'year':
                this.state.currentDate = moment(this.state.currentDate).add(step, 'years');
                break;
        }
        this.updateDateRange();
        this.fetchData();
    }

    changeTimeScale(newScale) {
        this.state.currentScale = newScale.toLowerCase();
        this.updateDateRange();
        this.fetchData();
    }

    getCurrentRange() {
        return {
            start_date: this.state.startDate,
            end_date: this.state.endDate,
            scale: this.state.currentScale
        };
    }
    async fetchData() {
        const { startDate, endDate, currentScale } = this.state;
        try {
            if (this.props.action.context.id) {
                const result = await this.rpc('/get/project-gantt/data', {
                    id: this.props.action.context.id,
                    start_date: startDate,
                    end_date: endDate,
                    scale: currentScale
                });
                this.state.data = result;
                this.renderGantt(result)
            }


        } catch (error) {
            console.error("Error fetching data:", error);
        }
    }
    async showJobOrderPopup(taskName, model) {
        try {
            const domain = [['id', '=', parseInt(taskName)]];
            const records = await this.orm.searchRead(model, domain, ['id', 'name', 'task_id']);

            if (records && records.length > 0) {
                this.state.selectedJobOrder = {
                    id: records[0].id,
                    name: records[0].name,
                    task_id: records[0].task_id,
                    model: model
                };
                this.state.showJobOrderPopup = true;
            }
        } catch (error) {
            console.error('Error fetching job order details:', error);
        }
    }

    closeJobOrderPopup() {
        this.state.showJobOrderPopup = false;
        this.state.selectedJobOrder = null;
    }
      async viewWorkOrder() {
        if (!this.state.selectedJobOrder) return;

        try {
            await this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Work Orders',
                res_model: 'job.order',
                res_id: this.state.selectedJobOrder.id,
                view_mode: 'form',
                views: [[false, 'form']],
                target: 'current',
                context: { 'create': false }
            });

            this.closeJobOrderPopup();
        } catch (error) {
            console.error('Error opening work order:', error);
        }
    }

    async viewTask() {
        if (!this.state.selectedJobOrder) return;

        try {
            const taskModel = 'project.task'
            const taskDomain = [['job_order_id', '=', this.state.selectedJobOrder.id]];
             const record = await this.orm.searchRead(taskModel, taskDomain, ['id']);

            await this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Tasks',
                res_model: taskModel,
                view_mode: 'form',
                views: [[false, 'form']],
                res_id: record[0].id,
                target: 'current',
                context: { 'create': false }
            });

            this.closeJobOrderPopup();
        } catch (error) {
            console.error('Error opening task:', error);
        }
    }

    renderGantt(data) {
        console.log('.....................................', data)
        let el = document.getElementById('project-chart');
        if (el.innerHTML != '') {
            gantt.clearAll();
            el.innerHTML = '';
        }

        var tasks = {
            data: data['data'],
            links: data['links']
        };
        const handleTaskClick = async (taskName, model) => {
            if (!taskName || !model) return;
            if (model == 'job.order') {
                this.showJobOrderPopup(taskName, model);
            }
            else {
                try {
                    const domain = [['id', '=', parseInt(taskName)]];
                    const records = await this.orm.searchRead(model, domain, ['id']);

                    if (records && records.length > 0) {
                        let context = { 'create': false };
                        return await this.action.doAction({
                            type: 'ir.actions.act_window',
                            name: taskName,
                            res_model: model,
                            res_id: records[0].id,
                            view_mode: 'form',
                            views: [[false, 'form']],
                            target: 'current',
                            context: context,
                        });
                    }
                } catch (error) {
                    console.error('Error opening record:', error);
                }
            }

        };
        gantt.templates.task_text = function (start, end, task) {
            const start_date = new Date(task.start_date); // Replace with your given date
            const options = { day: '2-digit', month: 'short', year: 'numeric' };
            const formattedStartDate = start_date.toLocaleDateString('en-GB', options);
            const end_date = new Date(task.end_date);
            const formattedEndDate = end_date.toLocaleDateString('en-GB', options);

            return `<div class="task-text" data-task-name="${task.code || ''}" data-task-model='${task.model || ''}'>${task.text}</div>`;
        };
//         Configure Gantt chart settings
        gantt.config.min_column_width = 50;
        gantt.config.readonly = true;
        gantt.config.columns = [
            { name: "text", label: "Orders", width: 200, tree: true },
            { name: "start_date", label: "Start date", align: "center", width: 100 },
            { name: "end_date", label: "End date", align: "center", width: 100 },
            { name: "duration", label: "Duration", align: "center", width: 70 }
        ];
        const today = new Date();
        // Custom templates for grid display
        gantt.templates.grid_folder = function (item) {
            return " ";
        };

        gantt.templates.grid_file = function (item) {
            return " ";
        };
        gantt.plugins({
            marker: true
        });
        let scale = this.state.currentScale
        gantt.templates.scale_cell_class = function (date) {
            if (scale != 'year') {
                if (
                    date.getDate() === today.getDate() &&
                    date.getMonth() === today.getMonth() &&
                    date.getFullYear() === today.getFullYear()
                ) {
                    return "today-column";
                }
            } else {
                if (
                    date.getMonth() === today.getMonth() &&
                    date.getFullYear() === today.getFullYear()
                ) {
                    return "today-column";
                }
            }


            return "";
        };
        gantt.templates.timeline_cell_class = function (item, date) {
            if (scale != 'year') {
                if (
                    date.getDate() === today.getDate() &&
                    date.getMonth() === today.getMonth() &&
                    date.getFullYear() === today.getFullYear()
                ) {
                    return "today-marker";
                }
            } else {
                if (
                    date.getMonth() === today.getMonth() &&
                    date.getFullYear() === today.getFullYear()
                ) {
                    return "today-marker";
                }
            }
            return "";
        };


        gantt.config.start_date = this.state.startDate;
        gantt.config.end_date = this.state.endDate;
        switch (this.state.currentScale) {
            case 'day':
                this.configureForDayScale();
                break;
            case 'week':
                this.configureForWeekScale();
                break;
            case 'month':
                this.configureForMonthScale();
                break;
            case 'year':
                this.configureForYearScale();
                break;
        }
        gantt.init(el);
        gantt.parse(tasks);
        el.addEventListener('click', function (event) {
            if (event.target.classList.contains('task-text')) {
                const taskId = event.target.getAttribute('data-task-name');
                const model = event.target.getAttribute('data-task-model');
                if (taskId && model) {
                    handleTaskClick(taskId, model);
                }
            }
        });
    }
    configureForDayScale() {
        gantt.config.scale_unit = "day";
        gantt.config.date_scale = "%d %M %Y";
    }


    configureForWeekScale() {
        gantt.config.scale_unit = "day";
        gantt.config.date_scale = "%d %M";
    }


    configureForMonthScale() {
        gantt.config.scale_unit = "day";
        gantt.config.date_scale = "%d %M";
    }

    configureForYearScale() {
        gantt.config.scale_unit = "month";
        gantt.config.date_scale = "%F %Y";
    }
}

PropertyProject.template = "tk_construction_management.project_gantt_view";
registry.category("actions").add("project_gantt", PropertyProject);
