with main_table as (

    select * from {{ref('stg__station_status') }}
),

join_table as (

    select * from {{ ref('stg__station_information') }}
)


select
    m.station_id,
    j.station_name,
    m.num_vehicles_available,
    m.num_docks_available,
    m.is_renting,
    m.is_returning,
    m.snapshot_at,
    j.capacity,
    j.latitude,
    j.longitude,
    round(({{ dbt_utils.safe_divide('m.num_vehicles_available ', 'j.capacity') }} * 100),2) as occupancy_percentage,
    case
        when j.station_id is not null then true
        else false
    end as is_listed_station

from main_table as m
left join join_table as j
    on m.station_id = j.station_id
