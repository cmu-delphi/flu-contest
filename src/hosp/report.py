# first party
import flu_contest.src.hosp.tools as tools
import flu_contest.src.hosp.hosp_utils as hosp_utils
import flu_contest.src.hosp.preparation as preparation

import matplotlib.pyplot as plt
from matplotlib import colors
# third party
import numpy as np

def plot_empty_rate(data, time_periods):
    years = []
    empty_rates = {}

    for time_period in time_periods:
        start_yr, _ = hosp_utils.get_season(time_period)
        years.append(str(start_yr))

        for location in hosp_utils.STATE_LIST:
            total_count, failure_count = 0, 0

            for group in range(5):
                period = hosp_utils.unravel(time_period)

                for epiweek in period:
                    key = (epiweek, group, location)

                    if key in data:
                        cur_data = data[key][-1]
                        total_count += 1

                        if cur_data == 0.0:
                            failure_count += 1

                failure_rate = failure_count / total_count
                if (location, group) not in empty_rates:
                    empty_rates[(location, group)] = []
                
                empty_rates[(location, group)].append(failure_rate)
    
    inds = range(len(years))

    for location in hosp_utils.STATE_LIST:
        plt.figure()
        plt.xticks(inds, years)
        plt.xlabel('season')
        plt.ylabel('empty rate')
        plt.title(location)

        for group in range(5):
            plt.plot(inds, empty_rates[(location, group)], 
                                label=hosp_utils.GROUP_DESCRIPTION[group])
        
        plt.legend()
        plt.savefig(location + '.png', dpi=300)
        plt.close()

def plot_backfill_rate(data, time_periods):
    years = []
    backfill_rates = {}

    for time_period in time_periods:
        start_yr, _ = hosp_utils.get_season(time_period)
        years.append(str(start_yr))

        for location in hosp_utils.STATE_LIST:
            for group in range(5):
                period = hosp_utils.unravel(time_period)
                first_sum, final_sum = 0.0, 0.0

                for epiweek in period:
                    key = (epiweek, group, location)

                    if key in data:
                        final_sum += data[key][-1]
                        first_sum += data[key][0]
                
                bf_rate = 1 - first_sum / final_sum

                if (location, group) not in backfill_rates:
                    backfill_rates[(location, group)] = []
                backfill_rates[(location, group)].append(bf_rate)
    
    inds = range(len(years))

    for location in hosp_utils.STATE_LIST:
        plt.figure()
        plt.xticks(inds, years)
        plt.xlabel('season')
        plt.ylabel('backfill rate')
        plt.title(location)

        for group in range(5):
            plt.plot(inds, backfill_rates[(location, group)], 
                                label=hosp_utils.GROUP_DESCRIPTION[group])
        
        plt.legend()
        plt.savefig(location + '.png', dpi=300)
        plt.close()

def plot_backfill(data, time_period):
    
    period = hosp_utils.unravel(time_period)
    location = 'network_all'

    valid_weeks = []
    cur_truth = [[], [], [], [], []]
    ground_truth = [[], [], [], [], []]
    
    for epiweek in period:
        valid_weeks.append(epiweek)

        for group in range(5):
            _, cur_y_val, y_val = preparation.fetch(data, location, group, epiweek, 
                                    lag=0, left_window=0, right_window=0, backfill_window=0)
            cur_truth[group].append(cur_y_val)
            ground_truth[group].append(y_val)

    inds = range(len(valid_weeks))
    week_ticks = [str(epiweek % 100) for epiweek in valid_weeks]
    start_yr, end_yr = hosp_utils.get_season(time_period)

    for group in range(5):
        title = 'Season: ' + str(start_yr) + '-' + str(end_yr) + ', ' + \
                hosp_utils.GROUP_DESCRIPTION[group]
        backfill = np.array(ground_truth[group]).squeeze() - np.array(cur_truth[group]).squeeze()
        ymax = np.max(np.array(ground_truth[group])) + 0.5

        plt.figure()
        plt.ylim(bottom=0, top=ymax)
        plt.plot(inds, cur_truth[group], label='first issue')
        plt.plot(inds, ground_truth[group], label='final rate')
        plt.bar(inds, backfill, width=0.1, bottom=cur_truth[group], color='g', label='backfill')
        plt.xticks(inds, week_ticks, rotation='vertical')
        plt.xlabel('weeks')
        plt.ylabel('hospitalization rate')
        plt.title(title)
        plt.legend()

        plt.savefig(str(group) + '.png', dpi=300)

def plot_selection(w, t, offset):
    cmap = colors.ListedColormap(['white', '#cc002b'])
    data = np.zeros((w, w))
    info = [[] for _ in range(w)]
    x_labels = [str(offset + x) for x in range(0, w)]+ ['e']
    y_labels = [str(offset + x) for x in range(w - 1, -1, -1)]

    fig, ax = plt.subplots()
    ax.set_xlabel('epiweek')
    ax.set_ylabel('release time')

    ax.set_yticks(range(w))
    ax.set_yticklabels(y_labels)

    ax.set_xticks(range(w))
    ax.set_xticklabels(x_labels)
    ax.set_title('Example: w = ' + str(w) + ', ' + 't = ' + str(t) +
                ', epiweek = ' + str(w - 1 + offset) )

    for j in range(t):
        data[j][0: w-j] = 10000.0

        for i in range(j, w):
            info[j].insert(0, str(offset + w - 1 - i) + ';' + str(i - j))

    plt.imshow(data, cmap=cmap)
    for j in range(t):
        for i in range(w - j):
            ax.text(i, j, info[j][i], ha='center', va='center', color='w')

    fig.tight_layout()
    plt.savefig('example.png', dpi=300)
